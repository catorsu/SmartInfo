"""
Workflow for fetching news.
"""

import json
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

from core.llm.pool import LLMClientPool
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
from urllib.parse import urlparse
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
    llm_pool: LLMClientPool,
    exclude_links: Optional[List[str]] = None,
    progress_callback: Optional[
        Callable[[Union[int, str], float, str, int], None]
    ] = None,
) -> List[Dict[str, str]]:
    """
    Fetch news from a given URL using a crawler and an LLM client.

    Args:
        url: The URL of the news to fetch.
        llm_pool: The LLM pool to use for fetching the news.
        exclude_links: The links to exclude from the news.
        progress_callback: The callback to use for updating the progress of the news fetch.
            Accepts arguments: step, progress_percent, message, items_count=0

    Returns:
        A list of dictionaries containing the news summary.
        Each dictionary contains the following keys:
            - title: The title of the news.
            - url: The URL of the news.
            - date: The date of the news.
            - summary: The summary of the news.
            - content: The content of the news.
    """
    start_time = time.time()
    logger.info(f"Starting processing for URL: {url}")

    if progress_callback:
        await progress_callback(CRAWLING, 10, f"Crawling page: {url}")

    crawler_result = None
    logger.debug(f"Starting crawl with Playwright: {url}")
    try:
        async with PlaywrightCrawler() as crawler:
            crawler_result = await crawler.fetch_single(url)
            logger.debug(f"Playwright crawl completed: {url}")
    except Exception as e:
        logger.error(f"Playwright crawl failed: {url}, Error: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to crawl {url}: {str(e)}")

    if not crawler_result or crawler_result.get("error"):
        error_msg = (
            crawler_result.get("error", "Unknown error")
            if crawler_result
            else "Empty result"
        )
        logger.error(f"Crawl result contains error: {url}, Error: {error_msg}")
        raise ValueError(f"Failed to crawl {url}: {error_msg}")

    html_content = crawler_result.get("content", "")

    if not html_content:
        logger.error(f"Crawled HTML content is empty: {url}")
        raise ValueError(f"Failed to crawl {url}")

    logger.debug(f"Starting HTML cleaning and conversion to Markdown: {url}")
    cleaned_markdown = _clean_and_prepare_markdown(
        url=url, html_content=html_content, exclude_links=exclude_links
    )

    if not cleaned_markdown:
        logger.error(f"HTML cleaning failed: {url}")
        return []

    if progress_callback:
        await progress_callback(
            EXTRACTING_LINKS, 20, "Extracting article links from page"
        )

    token_size = get_token_size(cleaned_markdown)
    logger.debug(f"Markdown Token count: {url}, Total {token_size} tokens")

    markdown_chunks = [cleaned_markdown]
    num_chunks = 1
    if token_size > llm_pool._max_input_tokens:
        num_chunks = (token_size // llm_pool._max_input_tokens) + 1
        logger.debug(
            f"Content exceeds context window size, needs chunking: {url}, Divided into {num_chunks} chunks"
        )

        if progress_callback:
            await progress_callback(
                EXTRACTING_LINKS,
                25,
                f"Page content is large, splitting into {num_chunks} parts for processing",
            )
        try:

            logger.debug(f"Starting content chunking: {url}")
            markdown_chunks = get_chunks(cleaned_markdown, num_chunks)
            logger.debug(
                f"Content chunking completed: {url}, Actually generated {len(markdown_chunks)} chunks"
            )
        except Exception as e:

            logger.error(
                f"Content chunking failed: {url}, Error: {str(e)}", exc_info=True
            )
            markdown_chunks = [cleaned_markdown]
            num_chunks = 1
            if progress_callback:
                await progress_callback(
                    EXTRACTING_LINKS,
                    25,
                    f"Content splitting failed, will process as a single chunk: {str(e)}",
                )

    original_content_metadata_dict: Dict[str, Dict[str, str]] = {}

    chunk_count = len(markdown_chunks)
    logger.debug(f"Preparing to process {chunk_count} content chunks: {url}")

    for i, chunk_content in enumerate(markdown_chunks):
        if not chunk_content.strip():
            logger.warning(
                f"Skipping empty chunk: {url}, Chunk index: {i+1}/{chunk_count}"
            )
            continue

        logger.debug(
            f"Starting to process content chunk {i+1}/{chunk_count}: {url}, Chunk size: {len(chunk_content)} bytes"
        )

        if progress_callback and chunk_count > 1:
            await progress_callback(
                EXTRACTING_LINKS,
                30 + (i * 10 / chunk_count),
                f"Processing page chunk {i+1}/{chunk_count}",
            )

        logger.debug(
            f"Starting link extraction and crawling: {url}, Chunk {i+1}/{chunk_count}"
        )
        sub_original_content_metadata_dict = await _extract_and_crawl_links(
            url, chunk_content, llm_pool
        )

        if not sub_original_content_metadata_dict:

            logger.warning(
                f"No valid links found in chunk: {url}, Chunk {i+1}/{chunk_count}"
            )
            continue

        found_count = len(sub_original_content_metadata_dict)
        logger.debug(
            f"Found {found_count} valid links in chunk {i+1}/{chunk_count}: {url}"
        )
        original_content_metadata_dict.update(sub_original_content_metadata_dict)

    total_articles = len(original_content_metadata_dict)
    logger.info(f"All chunks processed, Total {total_articles} articles found: {url}")

    if not original_content_metadata_dict:
        logger.error(f"No valid content found: {url}")
        return []

    if progress_callback:
        await progress_callback(
            ANALYZING,
            60,
            f"Found {len(original_content_metadata_dict)} articles, performing analysis and summarization",
        )

    logger.info(f"Starting summarization for {total_articles} articles: {url}")
    summary_result = await summarize_content(
        url=url,
        original_content_metadata_dict=original_content_metadata_dict,
        llm_pool=llm_pool,
    )

    summary_count = len(summary_result) if summary_result else 0
    logger.info(
        f"Summarization completed, Successfully processed {summary_count} articles: {url}"
    )

    if not summary_result:
        logger.error(f"Summarization failed or result is empty: {url}")
        return []

    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(
        f"Finished processing URL: {url}, Time taken: {elapsed_time:.2f} seconds, Processed {summary_count} articles"
    )

    if progress_callback:
        await progress_callback(
            SAVING,
            90,
            f"Completed extraction and summarization for {len(summary_result)} articles",
        )

    return summary_result


def _clean_and_prepare_markdown(
    url: str, html_content: str, exclude_links: Optional[List[str]] = None
) -> Optional[str]:
    """
    Clean raw HTML and convert it into Markdown format.
    - Removes unwanted tags/styles.
    - Normalizes links.

    Args:
        url: The URL of the news.
        html_content: The HTML content of the news.
        exclude_links: The links to exclude from the news.

    Returns:
        The cleaned and prepared markdown content.
    """
    logger.debug(
        f"Starting HTML content cleaning: {url}, HTML length: {len(html_content)} bytes"
    )
    try:

        logger.debug(f"Converting HTML to Markdown: {url}")
        cleaned_markdown = clean_and_format_html(
            html_content=html_content,
            base_url=url,
            output_format="markdown",
        )
        logger.debug(
            f"HTML conversion completed, Markdown length: {len(cleaned_markdown)} bytes"
        )

        logger.debug(f"Removing image links: {url}")
        cleaned_markdown = strip_image_links(cleaned_markdown)

        logger.debug(f"Removing JavaScript links: {url}")
        cleaned_markdown = strip_javascript_links(cleaned_markdown)

        cleaned_markdown = strip_extra_links_from_markdown(
            cleaned_markdown, exclude_urls=exclude_links, base_url=url
        )

        logger.debug(f"HTML cleaning completed: {url}")
        return cleaned_markdown
    except Exception as e:
        logger.error(
            f"Error during HTML cleaning/formatting: {url}: {e}", exc_info=True
        )
        return None


def build_link_extraction_prompt(url: str, markdown_content: str) -> str:
    prompt = f"""
<Base URL>
{url}
</Base URL>
<Markdown content>
{markdown_content}
</Markdown content>
"""
    logger.debug(f"Building link extraction prompt, Length: {len(prompt)} bytes")
    return prompt


def build_content_analysis_prompt(
    original_content_metadata_dict: Dict[str, Dict[str, str]],
) -> str:
    if not original_content_metadata_dict:
        logger.warning(
            "No article metadata provided, cannot build content analysis prompt"
        )
        return ""

    prompt_parts: List[str] = []
    article_count = len(original_content_metadata_dict)
    logger.debug(f"Building content analysis prompt, Total {article_count} articles")

    for article_url, data in original_content_metadata_dict.items():
        prompt_parts.append("<Article>")
        prompt_parts.append(f"Title: {data.get('title', 'Untitled')}")
        prompt_parts.append(f"Url: {data.get('url', article_url)}")
        prompt_parts.append(f"Date: {data.get('date', 'N/A')}")
        prompt_parts.append("Content:")
        prompt_parts.append(data.get("content", ""))
        prompt_parts.append("</Article>\n")

    prompt_parts.append(
        "Please summarize each article in Markdown format, following the structure and style shown above."
    )
    prompt = "\n".join(prompt_parts)
    logger.debug(f"Content analysis prompt built, Length: {len(prompt)} bytes")
    return prompt


async def _extract_and_crawl_links(
    base_url: str,
    markdown_content: str,
    llm_pool: LLMClientPool,
) -> Dict[str, Dict[str, str]]:
    """
    Extracts article links from Markdown using LLM and fetches sub-article content.
    Returns a mapping from sub-URL to its extracted metadata.
    """
    sub_original_content_metadata_dict: Dict[str, Dict[str, str]] = {}
    logger.debug(
        f"Starting link extraction from Markdown: {base_url}, Markdown length: {len(markdown_content)} bytes"
    )

    try:

        logger.debug(f"Building LLM prompt for link extraction: {base_url}")
        link_prompt = build_link_extraction_prompt(base_url, markdown_content)

        logger.debug(f"Requesting LLM to identify article links in page: {base_url}")
        links_str = await llm_pool.get_completion_content(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACT_ARTICLE_LINKS},
                {"role": "user", "content": link_prompt},
            ],
            max_tokens=4096,
            temperature=0.0,
        )
        logger.debug(
            f"LLM returned raw link result, Length: {len(links_str) if links_str else 0} bytes"
        )

        if not links_str or not links_str.strip() or links_str.strip() == "no":
            logger.warning(
                f"LLM found no links: {base_url}, Skipping link extraction and crawling"
            )
            return sub_original_content_metadata_dict

        logger.debug(
            f"Starting processing and normalization of LLM extracted links: {base_url}"
        )
        extracted_links = []
        for link in links_str.splitlines():
            link = link.strip()
            if not link or link == base_url:
                continue

            normalized_url = urljoin(base_url, link)

            parsed_url = urlparse(normalized_url)
            if parsed_url.scheme and parsed_url.netloc:
                extracted_links.append(normalized_url)
                logger.debug(f"Extracted valid link: {normalized_url}")
            else:
                logger.debug(f"Ignoring invalid link: {link} -> {normalized_url}")

        if not extracted_links:
            logger.warning(
                f"No valid links found: {base_url}, Skipping link extraction and crawling"
            )
            return sub_original_content_metadata_dict

        logger.debug(
            f"Found {len(extracted_links)} valid links, Starting crawl: {base_url}"
        )

        async with AiohttpCrawler() as sub_crawler:
            processed_count = 0
            total_links = len(extracted_links)

            async for crawl_result in sub_crawler.process_urls(
                extracted_links, max_retries=1
            ):
                processed_count += 1
                logger.debug(
                    f"Crawl progress: {processed_count}/{total_links} ({processed_count*100/total_links:.1f}%)"
                )

                if crawl_result.get("error") or not crawl_result.get("content"):
                    error_msg = crawl_result.get("error", "内容为空")
                    orig_url = crawl_result.get("original_url", "Unknown URL")
                    logger.warning(
                        f"Sub-link crawl failed: {orig_url}, Error: {error_msg}"
                    )
                    continue

                sub_url = crawl_result.get(
                    "final_url", crawl_result.get("original_url")
                )
                if not sub_url:
                    logger.warning(
                        "URL information missing in crawl result, skipping this result"
                    )
                    continue

                logger.debug(f"Extracting metadata from HTML: {sub_url}")
                structure_data = extract_metadata_combined_newspaper4k_trafilatura(
                    html_content=crawl_result["content"],
                    base_url=sub_url,
                )
                if not structure_data:
                    logger.warning(f"Cannot extract metadata from HTML: {sub_url}")
                    continue

                title = structure_data.get("title", "无标题")
                content_length = len(structure_data.get("content", ""))
                logger.debug(
                    f"Successfully extracted article: {sub_url}, Title: {title}, Content length: {content_length} bytes"
                )
                sub_original_content_metadata_dict[sub_url] = structure_data

        logger.debug(
            f"Sub-link crawling completed: {base_url}, Successfully crawled {len(sub_original_content_metadata_dict)}/{total_links} sub-links"
        )

    except Exception as e:
        logger.error(
            f"Error during link extraction and crawling: {base_url}: {e}",
            exc_info=True,
        )
        return sub_original_content_metadata_dict

    return sub_original_content_metadata_dict


async def summarize_content(
    url: str,
    original_content_metadata_dict: Dict[str, Dict[str, str]],
    llm_pool: LLMClientPool,
) -> List[Dict[str, str]]:
    """
    Args:
        url: The URL of the news.
        original_content_metadata_dict: A dictionary containing the original content metadata.
        llm_client: The LLM client to use for summarization.
        progress_callback: Optional callback for progress updates.

    Returns:
        A list of dictionaries containing the news summary.
        Each dictionary contains the following keys:
            - title: The title of the news.
            - url: The URL of the news.
            - date: The date of the news.
            - summary: The summary of the news.
            - content: The content of the news.
    """
    analysis_result: List[Dict[str, str]] = []
    article_count = len(original_content_metadata_dict)

    logger.info(
        f"Starting content summarization: {url}, Number of articles: {article_count}"
    )

    analysis_prompt = build_content_analysis_prompt(original_content_metadata_dict)
    prompt_tokens = get_token_size(analysis_prompt)
    logger.debug(f"Content analysis prompt Token count: {prompt_tokens}")

    try:

        if prompt_tokens > llm_pool._max_input_tokens:
            logger.debug(
                f"Prompt exceeds context window limit ({prompt_tokens} > {llm_pool._max_input_tokens}), needs chunking"
            )
            num_prompt_chunks = (prompt_tokens // llm_pool._max_input_tokens) + 1
            logger.debug(
                f"Planned to divide into {num_prompt_chunks} chunks for processing"
            )

            chunk_maps: List[Dict[str, Dict[str, str]]] = []
            keys = list(original_content_metadata_dict.keys())
            total = len(keys)

            if total < num_prompt_chunks:
                logger.error(
                    f"Token count exceeded, but number of articles ({total}) is less than number of chunks ({num_prompt_chunks}), cannot effectively chunk"
                )
                raise ValueError(
                    f"Token limit exceeded, not enough content to chunk for {url}."
                )

            logger.debug(
                f"Each chunk will contain approximately {total // num_prompt_chunks} articles"
            )
            size = total // num_prompt_chunks
            for i in range(num_prompt_chunks):
                start = i * size
                end = start + size if i < num_prompt_chunks - 1 else total
                part_keys = keys[start:end]
                if part_keys:
                    chunk_maps.append(
                        {k: original_content_metadata_dict[k] for k in part_keys}
                    )
                    logger.debug(
                        f"Chunk {i+1} contains {len(part_keys)} articles, from index {start} to {end-1}"
                    )

            # Build separate prompts for each chunk
            prompt_chunks = [
                build_content_analysis_prompt(chunk_map) for chunk_map in chunk_maps
            ]
            logger.debug(
                f"Created {len(prompt_chunks)} prompt chunks, preparing for batch processing: {url}"
            )

            for i, p_chunk in enumerate(prompt_chunks):
                logger.debug(
                    f"Starting to process prompt chunk {i+1}/{len(prompt_chunks)}"
                )

                llm_result = await llm_pool.get_completion_content(
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH,
                        },
                        {"role": "user", "content": p_chunk},
                    ],
                    max_tokens=llm_pool._max_output_tokens,
                    temperature=0.8,
                )
                logger.debug(
                    f"Chunk {i+1} LLM returned result length: {len(llm_result)} bytes"
                )

                try:
                    json_result = parse_json_from_text(llm_result)
                    result_count = len(json_result) if json_result else 0
                    logger.debug(
                        f"Successfully parsed {result_count} article summaries from chunk {i+1}"
                    )
                    analysis_result.extend(json_result)

                except json.JSONDecodeError as je:
                    logger.error(
                        f"Chunk {i+1} JSON parsing failed: {url}, Error location: {str(je)}"
                    )
                    logger.debug(
                        f"Raw content of failed JSON parsing: {llm_result[:500]}..."
                    )
                except Exception as e:
                    logger.error(
                        f"Error during chunk {i+1} processing: {url}: {e}",
                        exc_info=True,
                    )

        else:
            logger.debug(
                f"Prompt within Token limit, processing as single batch: {url}"
            )
            llm_result = await llm_pool.get_completion_content(
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH,
                    },
                    {"role": "user", "content": analysis_prompt},
                ],
                max_tokens=llm_pool._max_output_tokens,
                temperature=0.8,
            )
            logger.debug(f"LLM returned result length: {len(llm_result)} bytes")

            try:
                analysis_result = parse_json_from_text(llm_result)
                result_count = len(analysis_result) if analysis_result else 0
                logger.debug(f"Successfully parsed {result_count} article summaries")

            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing failed: {url}, Error location: {str(je)}")
                logger.debug(f"JSON解析失败的原始内容: {llm_result[:500]}...")
            except Exception as e:
                logger.error(f"Error during processing: {url}: {e}", exc_info=True)

    except Exception as analyze_err:

        logger.error(f"Error during LLM analysis: {url}: {analyze_err}", exc_info=True)

    logger.debug(
        f"Starting to process final result, currently have {len(analysis_result)} article summaries"
    )
    filtered_result = []
    missing_url_count = 0

    for result_item in analysis_result:
        url_key = result_item.get("url", "")
        if url_key:

            result_item["date"] = original_content_metadata_dict.get(url_key, {}).get(
                "date", ""
            )
            result_item["content"] = original_content_metadata_dict.get(
                url_key, {}
            ).get("content", "")
            result_item["top_image"] = original_content_metadata_dict.get(
                url_key, {}
            ).get("top_image", "")

            title = result_item.get("title", "Untitled")
            summary_length = len(result_item.get("summary", ""))
            logger.debug(
                f"Adding article to final result: {url_key}, Title: {title}, Summary length: {summary_length} bytes"
            )
            filtered_result.append(result_item)
        else:
            missing_url_count += 1
            logger.warning(
                f"Ignoring result item missing URL: {result_item.get('title', 'Untitled')}"
            )

    logger.info(
        f"Final result processing completed: {url}, Total {len(filtered_result)} valid articles, Ignored {missing_url_count} articles without URL"
    )
    return filtered_result
