"""
News Fetching and Processing Workflow for SmartInfo.

This module orchestrates the process of fetching news content from a given URL,
extracting relevant article links, crawling those articles, and then using
Large Language Models (LLMs) to summarize the content and generate fact-based titles.
It is designed to be used within background tasks (e.g., Celery) and provides
progress reporting capabilities.

Key Components/Exports:
  - fetch_news: The main public function that drives the entire news fetching
                and summarization workflow for a single source URL.
"""

import json
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple, Union, Awaitable
from urllib.parse import urljoin, urlparse

from core.llm.client import AsyncLLMClient
from utils.html_utils import (
    clean_and_format_html,
    extract_metadata_combined_newspaper4k_trafilatura,
)
from utils.markdown_utils import (
    strip_extra_links_from_markdown,
    strip_javascript_links,
    strip_image_links,
)
from utils.parse import parse_json_from_text
from utils.prompt import (
    SYSTEM_PROMPT_EXTRACT_ARTICLE_LINKS,
    SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH,
)
from utils.text_utils import get_chunks
from utils.token_utils import get_token_size
from ..crawler import AiohttpCrawler, PlaywrightCrawler
from background.tasks.step_codes import (
    PREPARING,
    CRAWLING,
    EXTRACTING_LINKS,
    ANALYZING,
    SAVING,
    COMPLETE,
    ERROR,
)

logger = logging.getLogger(__name__)


async def fetch_news(
    url: str,
    llm_client: AsyncLLMClient,
    exclude_links: Optional[List[str]] = None,
    progress_callback: Optional[
        Callable[[Union[int, str], float, str, int], Awaitable[None]]
    ] = None,
) -> List[Dict[str, str]]:
    """
    Fetches, processes, and summarizes news articles from a given source URL.

    This function orchestrates the entire workflow:
    1. Crawls the main source URL to get its HTML content.
    2. Cleans the HTML and converts it to Markdown.
    3. Uses an LLM to extract potential article links from the Markdown.
    4. Crawls each extracted article link to get its content.
    5. Extracts metadata (title, date, content, top image) from each article.
    6. Uses an LLM to generate a new fact-based title and a summary for each article.
    7. Returns a list of processed articles.

    Args:
        url (str): The primary URL of the news source to fetch.
        llm_client (AsyncLLMClient): An initialized LLM client for making API calls. # Changed
        exclude_links (Optional[List[str]]): A list of URLs to ignore.
        progress_callback (Optional[Callable]): Async callback for progress.

    Returns:
        List[Dict[str, str]]: List of processed articles. Each dictionary contains:
            "url", "title", "summary", "date", "content", "top_image".
            Empty list on failure or no articles.

    Raises:
        ValueError: If the initial crawl of `url` fails.

    Side Effects:
        - HTTP requests to crawl URLs.
        - LLM API calls for link extraction and summarization.
        - Logs process details.
        - Invokes `progress_callback`.
    """
    start_time = time.time()
    logger.info(f"Starting processing for URL: {url}")

    if progress_callback:
        await progress_callback(CRAWLING, 10, f"Crawling page: {url}", 0)

    crawler_result: Optional[Dict[str, str]] = None
    logger.debug(f"Starting crawl with Playwright for main source URL: {url}")
    try:
        async with PlaywrightCrawler() as crawler:
            crawler_result = await crawler.fetch_single(url)
        logger.debug(f"Playwright crawl completed for main source URL: {url}")
    except Exception as e:
        logger.error(f"Playwright crawl failed for {url}: {str(e)}", exc_info=True)
        if progress_callback:
            await progress_callback(
                ERROR, 10, f"Failed to crawl main page: {str(e)}", 0
            )
        raise ValueError(f"Failed to crawl {url}: {str(e)}")

    if not crawler_result or crawler_result.get("error"):
        error_msg = (
            crawler_result.get("error", "Unknown error during crawl")
            if crawler_result
            else "Empty result from crawler"
        )
        logger.error(f"Crawl of {url} resulted in error: {error_msg}")
        if progress_callback:
            await progress_callback(ERROR, 10, f"Crawl error: {error_msg}", 0)
        raise ValueError(f"Failed to crawl {url}: {error_msg}")

    html_content = crawler_result.get("content", "")
    if not html_content:
        logger.error(f"Crawled HTML content is empty for {url}")
        if progress_callback:
            await progress_callback(ERROR, 10, "Crawled page content is empty", 0)
        raise ValueError(f"Crawled content for {url} is empty.")

    logger.debug(f"Starting HTML cleaning and conversion to Markdown for: {url}")
    cleaned_markdown_links_str = _clean_and_prepare_markdown(
        url=url, html_content=html_content, exclude_links=exclude_links
    )

    if not cleaned_markdown_links_str:
        logger.error(
            f"Markdown link preparation failed for {url}. No links to process."
        )
        if progress_callback:
            await progress_callback(
                EXTRACTING_LINKS, 20, "Content cleaning or link filtering failed", 0
            )
        return []

    if progress_callback:
        await progress_callback(
            EXTRACTING_LINKS, 20, "Extracting article links from page content", 0
        )

    token_size = get_token_size(cleaned_markdown_links_str)
    logger.debug(
        f"Token count for filtered Markdown links from {url}: {token_size} tokens."
    )

    markdown_link_chunks = [cleaned_markdown_links_str]
    if token_size > llm_client.max_input_tokens:
        num_chunks = (token_size // llm_client.max_input_tokens) + 1
        logger.debug(
            f"Filtered links string for {url} exceeds LLM context window ({token_size} > {llm_client.max_input_tokens}). "
            f"Splitting into {num_chunks} chunks."
        )
        if progress_callback:
            await progress_callback(
                EXTRACTING_LINKS,
                25,
                f"Link list is large, splitting into {num_chunks} parts for LLM processing.",
                0,
            )
        try:
            markdown_link_chunks = get_chunks(cleaned_markdown_links_str, num_chunks)
            logger.debug(
                f"Filtered links string for {url} split into {len(markdown_link_chunks)} actual chunks."
            )
        except Exception as e:
            logger.error(
                f"Link string chunking failed for {url}: {str(e)}. Processing as single chunk.",
                exc_info=True,
            )
            if progress_callback:
                await progress_callback(
                    EXTRACTING_LINKS,
                    25,
                    f"Link string splitting failed ({str(e)}), will process as a single large chunk.",
                    0,
                )

    original_content_metadata_dict: Dict[str, Dict[str, str]] = {}
    total_link_chunks_to_process = len(markdown_link_chunks)
    logger.debug(
        f"Preparing to process {total_link_chunks_to_process} link chunks for {url}."
    )

    for i, link_chunk_content in enumerate(markdown_link_chunks):
        if not link_chunk_content.strip():
            logger.warning(
                f"Skipping empty link chunk {i+1}/{total_link_chunks_to_process} for {url}."
            )
            continue

        logger.debug(
            f"Processing link chunk {i+1}/{total_link_chunks_to_process} for {url}. Chunk size: {len(link_chunk_content)} bytes."
        )
        if progress_callback and total_link_chunks_to_process > 1:
            chunk_progress = 30 + int((i / total_link_chunks_to_process) * 30)
            await progress_callback(
                EXTRACTING_LINKS,
                chunk_progress,
                f"Extracting final article links from content chunk {i+1}/{total_link_chunks_to_process}",
                0,
            )

        chunk_extracted_metadata = await _extract_and_crawl_links(
            url, link_chunk_content, llm_client
        )
        if chunk_extracted_metadata:
            original_content_metadata_dict.update(chunk_extracted_metadata)
            logger.debug(
                f"Extracted and crawled {len(chunk_extracted_metadata)} articles from link chunk {i+1}/{total_link_chunks_to_process} for {url}."
            )
        else:
            logger.warning(
                f"No articles extracted or crawled from link chunk {i+1}/{total_link_chunks_to_process} for {url}."
            )

    total_articles_found = len(original_content_metadata_dict)
    logger.info(
        f"Link extraction and crawling from all chunks for {url} complete. Found {total_articles_found} articles."
    )

    if not original_content_metadata_dict:
        logger.warning(
            f"No valid article content found after processing all link chunks for {url}."
        )
        if progress_callback:
            await progress_callback(
                COMPLETE, 100, "No new articles found or extracted.", 0
            )
        return []

    if progress_callback:
        await progress_callback(
            ANALYZING,
            60,
            f"Found {total_articles_found} articles. Starting summarization and title generation.",
            total_articles_found,
        )

    logger.info(
        f"Starting summarization for {total_articles_found} articles from {url}."
    )
    summary_result = await summarize_content(
        url=url,
        original_content_metadata_dict=original_content_metadata_dict,
        llm_client=llm_client,
    )

    summarized_articles_count = len(summary_result) if summary_result else 0
    logger.info(
        f"Summarization for {url} completed. Successfully summarized {summarized_articles_count} articles."
    )

    if not summary_result:
        logger.error(f"Summarization failed or returned empty result for {url}.")
        if progress_callback:
            await progress_callback(SAVING, 90, "Summarization yielded no results.", 0)
            await progress_callback(
                COMPLETE, 100, "Processing complete, no articles summarized.", 0
            )
        return []

    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(
        f"Finished processing URL: {url}. Time taken: {elapsed_time:.2f} seconds. "
        f"Summarized {summarized_articles_count} articles."
    )

    if progress_callback:
        await progress_callback(
            ANALYZING,
            90,
            f"Completed summarization for {summarized_articles_count} articles. Results ready.",
            summarized_articles_count,
        )

    return summary_result


def _clean_and_prepare_markdown(
    url: str, html_content: str, exclude_links: Optional[List[str]] = None
) -> Optional[str]:
    """
    Cleans raw HTML, converts to Markdown, and then filters links to prepare content for LLM link extraction.

    Args:
        url (str): The base URL of the HTML content.
        html_content (str): The raw HTML content.
        exclude_links (Optional[List[str]]): List of URLs to exclude.

    Returns:
        Optional[str]: String of Markdown-formatted links, or None on failure.
    Side Effects:
        - Logs cleaning and filtering stages.
    """
    logger.debug(
        f"Starting HTML content cleaning for URL: {url}. HTML length: {len(html_content)} bytes."
    )
    try:
        logger.debug(f"Converting HTML to Markdown for URL: {url}")
        full_markdown_content = clean_and_format_html(
            html_content=html_content,
            base_url=url,
            output_format="markdown",
        )
        logger.debug(
            f"HTML to Markdown conversion complete for {url}. Full Markdown length: {len(full_markdown_content)} bytes."
        )

        logger.debug(f"Removing image links from full Markdown for URL: {url}")
        markdown_no_images = strip_image_links(full_markdown_content)
        logger.debug(f"Removing JavaScript links from full Markdown for URL: {url}")
        markdown_basics_cleaned = strip_javascript_links(markdown_no_images)

        logger.debug(
            f"Extracting and filtering Markdown links from content of URL: {url}"
        )
        filtered_markdown_links_string = strip_extra_links_from_markdown(
            raw_text=markdown_basics_cleaned,
            exclude_urls=exclude_links,
            base_url=url,
        )

        if filtered_markdown_links_string:
            logger.debug(
                f"Markdown link filtering completed for URL: {url}. "
                f"Resulting link string length: {len(filtered_markdown_links_string)} bytes."
            )
        else:
            logger.warning(
                f"No relevant Markdown links found or extracted after filtering for URL: {url}."
            )
        return filtered_markdown_links_string

    except Exception as e:
        logger.error(
            f"Error during HTML cleaning/Markdown preparation for URL {url}: {e}",
            exc_info=True,
        )
        return None


def build_link_extraction_prompt(url: str, markdown_content: str) -> str:
    """
    Constructs the prompt for the LLM to extract article links from Markdown content.

    Args:
        url (str): The base URL of the source page.
        markdown_content (str): The Markdown content for link extraction.

    Returns:
        str: A formatted prompt string.
    Side Effects:
        - Logs prompt length and base URL.
    """
    prompt = f"""
<Base URL>
{url}
</Base URL>
<Markdown content>
{markdown_content}
</Markdown content>
"""
    logger.debug(
        f"Building link extraction prompt. Length: {len(prompt)} bytes. Base URL: {url}"
    )
    return prompt


def build_content_analysis_prompt(
    original_content_metadata_dict: Dict[str, Dict[str, str]],
) -> str:
    """
    Constructs the prompt for the LLM to summarize a batch of articles.

    Args:
        original_content_metadata_dict (Dict[str, Dict[str, str]]):
            Dictionary of article URLs to metadata.

    Returns:
        str: A formatted prompt string for batch summarization. Empty if input is empty.
    Side Effects:
        - Logs warnings and prompt details.
    """
    if not original_content_metadata_dict:
        logger.warning(
            "No article metadata provided; cannot build content analysis prompt."
        )
        return ""

    prompt_parts: List[str] = []
    article_count = len(original_content_metadata_dict)
    logger.debug(f"Building content analysis prompt for {article_count} articles.")

    for article_url, data in original_content_metadata_dict.items():
        prompt_parts.append("<Article>")
        prompt_parts.append(f"Title: {data.get('title', 'Untitled')}")
        prompt_parts.append(f"Url: {data.get('url', article_url)}")
        prompt_parts.append(f"Date: {data.get('date', 'N/A')}")
        prompt_parts.append("Content:")
        prompt_parts.append(data.get("content", ""))
        prompt_parts.append("</Article>\n")

    prompt = "\n".join(prompt_parts)
    logger.debug(
        f"Content analysis prompt built. Length: {len(prompt)} bytes for {article_count} articles."
    )
    return prompt


async def _extract_and_crawl_links(
    base_url: str,
    markdown_content: str,
    llm_client: AsyncLLMClient,
) -> Dict[str, Dict[str, str]]:
    """
    Extracts article links from Markdown using LLM, then crawls these links.

    Args:
        base_url (str): Base URL of the original source page.
        markdown_content (str): Markdown string of pre-filtered links.
        llm_client (AsyncLLMClient): Initialized LLM client.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary of crawled sub-article URLs to metadata.
                                   Empty if no links extracted or crawling/metadata fails.
    Side Effects:
        - LLM API call for link extraction.
        - HTTP requests via `AiohttpCrawler` for sub-articles.
        - Logs process details and errors.
    """
    sub_original_content_metadata_dict: Dict[str, Dict[str, str]] = {}
    logger.debug(
        f"Starting LLM-based link extraction from Markdown link string for base URL: {base_url}. "
        f"Link string length: {len(markdown_content)} bytes."
    )

    try:
        logger.debug(
            f"Building LLM prompt for link extraction from content related to: {base_url}"
        )
        link_prompt = build_link_extraction_prompt(base_url, markdown_content)

        logger.debug(
            f"Requesting LLM to identify final article links from provided Markdown links for: {base_url}"
        )
        links_str = await llm_client.get_completion_content(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACT_ARTICLE_LINKS},
                {"role": "user", "content": link_prompt},
            ],
            max_tokens=4096,
            temperature=0.0,
        )
        logger.debug(
            f"LLM returned raw link string for {base_url}. Length: {len(links_str) if links_str else 0} bytes."
        )

        if not links_str or not links_str.strip() or links_str.strip().lower() == "no":
            logger.warning(
                f"LLM found no suitable article links to extract from the provided list for {base_url}. "
                "Skipping sub-article crawling for this chunk."
            )
            return sub_original_content_metadata_dict

        logger.debug(f"Processing and normalizing LLM-selected links for {base_url}.")
        extracted_links: List[str] = []
        for link_line in links_str.splitlines():
            link = link_line.strip()
            if not link:
                continue

            normalized_url = urljoin(base_url, link)
            parsed_normalized_url = urlparse(normalized_url)

            if (
                parsed_normalized_url.scheme in ["http", "https"]
                and parsed_normalized_url.netloc
            ):
                if normalized_url != base_url:
                    extracted_links.append(normalized_url)
                    logger.debug(
                        f"Validated LLM-selected link: {normalized_url} (from LLM output: {link})"
                    )
                else:
                    logger.debug(
                        f"Ignoring LLM-selected link as it matches base_url: {normalized_url}"
                    )
            else:
                logger.debug(
                    f"Ignoring invalid or non-HTTP/S link from LLM: {link} (normalized: {normalized_url})"
                )

        unique_extracted_links = sorted(list(set(extracted_links)))

        if not unique_extracted_links:
            logger.warning(
                f"No valid, unique article links selected by LLM after normalization for {base_url}."
            )
            return sub_original_content_metadata_dict

        logger.debug(
            f"LLM selected {len(unique_extracted_links)} unique, valid links to crawl for {base_url}."
        )

        async with AiohttpCrawler() as sub_crawler:
            processed_count = 0
            total_links_to_crawl = len(unique_extracted_links)

            async for crawl_result in sub_crawler.process_urls(
                unique_extracted_links, max_retries=1
            ):
                processed_count += 1
                current_crawl_url = crawl_result.get("original_url", "Unknown URL")
                logger.debug(
                    f"Sub-article crawl progress for {base_url}: {processed_count}/{total_links_to_crawl} "
                    f"({(processed_count/total_links_to_crawl)*100:.1f}%) - Processing {current_crawl_url}"
                )

                if crawl_result.get("error") or not crawl_result.get("content"):
                    error_msg = crawl_result.get("error", "Content is empty")
                    logger.warning(
                        f"Sub-article crawl failed for {current_crawl_url} (from {base_url}): {error_msg}"
                    )
                    continue

                sub_article_final_url = crawl_result.get("final_url", current_crawl_url)
                if not sub_article_final_url:
                    logger.warning(
                        f"URL information missing in crawl result for an article from {base_url}, skipping."
                    )
                    continue

                logger.debug(
                    f"Extracting metadata from HTML for sub-article: {sub_article_final_url}"
                )
                structure_data = extract_metadata_combined_newspaper4k_trafilatura(
                    html_content=crawl_result["content"],
                    base_url=sub_article_final_url,
                )
                if not structure_data:
                    logger.warning(
                        f"Could not extract metadata from HTML for {sub_article_final_url}."
                    )
                    continue

                title = structure_data.get("title", "Untitled Article")
                content_len = len(structure_data.get("content", ""))
                logger.debug(
                    f"Successfully extracted metadata for: {sub_article_final_url}. Title: '{title}', Content length: {content_len} chars."
                )
                sub_original_content_metadata_dict[sub_article_final_url] = (
                    structure_data
                )

        logger.debug(
            f"Sub-article crawling and metadata extraction for {base_url} complete. "
            f"Successfully processed {len(sub_original_content_metadata_dict)}/{total_links_to_crawl} sub-articles."
        )

    except Exception as e:
        logger.error(
            f"Error during LLM link extraction and sub-article crawling for {base_url}: {e}",
            exc_info=True,
        )
        return sub_original_content_metadata_dict

    return sub_original_content_metadata_dict


async def summarize_content(
    url: str,
    original_content_metadata_dict: Dict[str, Dict[str, str]],
    llm_client: AsyncLLMClient,
) -> List[Dict[str, str]]:
    """
    Summarizes a batch of articles using an LLM.

    Args:
        url (str): Base URL of the original news source (for logging).
        original_content_metadata_dict (Dict[str, Dict[str, str]]):
            Dictionary of article URLs to metadata.
        llm_client (AsyncLLMClient): Initialized LLM client.

    Returns:
        List[Dict[str, str]]: List of summarized articles. Each includes:
            "url", "title", "summary", "date", "content", "top_image".
            Empty list on failure or no articles.
    Side Effects:
        - LLM API calls for summarization.
        - Logs process details and errors.
    """
    analysis_result: List[Dict[str, str]] = []
    article_count = len(original_content_metadata_dict)

    if article_count == 0:
        logger.warning(f"No articles provided for summarization from source {url}.")
        return []

    logger.info(
        f"Starting content summarization for {article_count} articles from source: {url}"
    )

    analysis_prompt = build_content_analysis_prompt(original_content_metadata_dict)
    if not analysis_prompt:
        logger.error(
            f"Failed to build analysis prompt for {url}, though articles were present."
        )
        return []

    prompt_tokens = get_token_size(analysis_prompt)
    logger.debug(f"Content analysis prompt for {url} has {prompt_tokens} tokens.")

    try:
        if prompt_tokens > llm_client.max_input_tokens:
            logger.warning(
                f"Batch prompt for {url} exceeds LLM context window ({prompt_tokens} > {llm_client.max_input_tokens}). "
                "Splitting articles into smaller sub-batches for summarization."
            )

            num_prompt_chunks = (prompt_tokens // llm_client.max_input_tokens) + 1
            logger.debug(
                f"Attempting to divide {article_count} articles into approx {num_prompt_chunks} sub-batches for {url}."
            )

            article_items = list(original_content_metadata_dict.items())
            actual_num_chunks = min(num_prompt_chunks, article_count)
            if actual_num_chunks <= 0:
                actual_num_chunks = 1

            articles_per_chunk = (
                article_count + actual_num_chunks - 1
            ) // actual_num_chunks

            for i in range(actual_num_chunks):
                start_index = i * articles_per_chunk
                end_index = min((i + 1) * articles_per_chunk, article_count)
                current_article_batch_items = article_items[start_index:end_index]

                if not current_article_batch_items:
                    continue

                current_batch_dict = dict(current_article_batch_items)
                chunk_prompt = build_content_analysis_prompt(current_batch_dict)

                logger.debug(
                    f"Processing sub-batch {i+1}/{actual_num_chunks} for {url} with {len(current_batch_dict)} articles. "
                    f"Prompt tokens: {get_token_size(chunk_prompt)}"
                )

                llm_result_chunk = await llm_client.get_completion_content(
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH,
                        },
                        {"role": "user", "content": chunk_prompt},
                    ],
                    max_tokens=llm_client.max_output_tokens,
                    temperature=0.8,
                )
                logger.debug(
                    f"Sub-batch {i+1} LLM response length: {len(llm_result_chunk)} bytes."
                )
                try:
                    json_chunk_result = parse_json_from_text(llm_result_chunk)
                    if json_chunk_result:
                        analysis_result.extend(json_chunk_result)
                        logger.debug(
                            f"Successfully parsed {len(json_chunk_result)} summaries from sub-batch {i+1} for {url}."
                        )
                except json.JSONDecodeError as je:
                    logger.error(
                        f"JSON parsing failed for sub-batch {i+1} from {url}: {str(je)}. "
                        f"Content snippet: {llm_result_chunk[:500]}..."
                    )
                except Exception as e_parse:
                    logger.error(
                        f"Error processing LLM result for sub-batch {i+1} from {url}: {e_parse}",
                        exc_info=True,
                    )
        else:
            logger.debug(
                f"Prompt for {url} is within token limits. Processing as single batch."
            )
            llm_result = await llm_client.get_completion_content(
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH,
                    },
                    {"role": "user", "content": analysis_prompt},
                ],
                max_tokens=llm_client.max_output_tokens,
                temperature=0.8,
            )
            logger.debug(f"LLM response length for {url}: {len(llm_result)} bytes.")
            try:
                analysis_result = parse_json_from_text(llm_result)
                logger.debug(
                    f"Successfully parsed {len(analysis_result)} summaries for {url}."
                )
            except json.JSONDecodeError as je:
                logger.error(
                    f"JSON parsing failed for {url}: {str(je)}. Content snippet: {llm_result[:500]}..."
                )
            except Exception as e_parse_single:
                logger.error(
                    f"Error processing LLM result for {url}: {e_parse_single}",
                    exc_info=True,
                )

    except ValueError as ve:
        logger.error(f"ValueError during summarization for {url}: {ve}", exc_info=True)
    except Exception as analyze_err:
        logger.error(
            f"Unexpected error during LLM summarization for {url}: {analyze_err}",
            exc_info=True,
        )

    logger.debug(
        f"Preparing to merge original metadata into {len(analysis_result)} summarized articles for {url}."
    )
    final_summarized_articles: List[Dict[str, str]] = []
    missing_url_in_summary_count = 0

    for summarized_item in analysis_result:
        article_url_from_summary = summarized_item.get("url")
        if (
            article_url_from_summary
            and article_url_from_summary in original_content_metadata_dict
        ):
            original_meta = original_content_metadata_dict[article_url_from_summary]

            final_item = {
                "url": article_url_from_summary,
                "title": summarized_item.get(
                    "title", original_meta.get("title", "Untitled")
                ),
                "summary": summarized_item.get("summary", ""),
                "date": original_meta.get("date", ""),
                "content": original_meta.get("content", ""),
                "top_image": original_meta.get("top_image", ""),
            }
            final_summarized_articles.append(final_item)
            logger.debug(
                f"Merged metadata for article: {article_url_from_summary}. LLM Title: '{final_item['title']}'"
            )
        else:
            missing_url_in_summary_count += 1
            logger.warning(
                f"Summarized item from LLM missing 'url' or URL '{article_url_from_summary}' "
                f"not found in original metadata for {url}. Title: '{summarized_item.get('title', 'N/A')}'. Skipping."
            )

    if missing_url_in_summary_count > 0:
        logger.warning(
            f"Skipped {missing_url_in_summary_count} summarized items due to missing/mismatched URLs for {url}."
        )

    logger.info(
        f"Metadata merging complete for {url}. Final count of summarized articles: {len(final_summarized_articles)}."
    )
    return final_summarized_articles
