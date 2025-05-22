"""
HTML processing utilities for the SmartInfo Backend.

This module provides functions for cleaning raw HTML content by removing
unwanted tags and elements, formatting cleaned HTML into Markdown or plain text,
and extracting structured metadata from article HTML using various libraries.

Key Functions:
    - clean_html: Removes specified HTML tags and elements selected by CSS.
    - format_html: Converts cleaned HTML to Markdown or plain text.
    - clean_and_format_html: A convenience function combining cleaning and formatting.
    - extract_metadata_from_article_trafilatura: Extracts metadata using Trafilatura.
    - extract_metadata_from_article_newspaper4k: Extracts metadata using Newspaper4k.
    - extract_metadata_combined_newspaper4k_trafilatura: Combines metadata from
      both Trafilatura and Newspaper4k, prioritizing Newspaper4k.

Default exclusion lists (`DEFAULT_EXCLUDE_TAGS`, `DEFAULT_EXCLUDE_SELECTORS`)
are provided for common use cases.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup
from markdownify import markdownify

# Import for newspaper4k will be within the function to keep startup light
# from newspaper import Article, ArticleException
# Import for trafilatura will be within the function
# from trafilatura import bare_extraction
# from trafilatura.metadata import Document


logger = logging.getLogger(__name__)

# Default list of HTML tags to be removed during the cleaning process.
# These tags typically do not contribute to the main textual content of an article
# (e.g., scripts, styles, navigation, forms, multimedia placeholders).
DEFAULT_EXCLUDE_TAGS = [
    # --- Scripts, styles, and metadata ---
    "script",
    "style",
    "link",
    "meta",
    "base",
    "noscript",
    "template",
    # --- Structural elements ---
    "header",
    "footer",
    "nav",
    "aside",
    # --- Forms and interactive elements ---
    "form",
    "input",
    "textarea",
    "select",
    "button",
    "label",
    "datalist",
    "meter",
    "progress",
    "dialog",
    # --- Media, embeds, and non-text content ---
    "audio",
    "video",
    "iframe",
    "embed",
    "object",
    "canvas",
    "map",
    "area",
    "source",
    "track",
    # --- Special handling tags ---
    "img",  # Images are often handled separately or converted to text representations
    "picture",
    "svg",
    "figure",
    "figcaption",
]

# Default list of CSS selectors for elements to be removed during cleaning.
# These selectors target common non-content sections like ads, menus,
# social media bars, comments, footers, popups, etc.
DEFAULT_EXCLUDE_SELECTORS = [
    # --- Ads and promotional content ---
    ".ad",
    ".ads",
    ".advert",
    ".advertisement",
    ".sponsored",
    ".promo",
    # --- Navigation and menus ---
    ".menu",
    ".nav",
    ".navigation",
    ".navbar",
    ".breadcrumbs",
    # --- Header and footer areas ---
    ".header",
    ".footer",
    ".site-header",
    ".site-footer",
    "#header",
    "#footer",
    "#site-header",
    "#site-footer",
    # --- Sidebars ---
    ".sidebar",
    ".widget",
    ".secondary",
    "#sidebar",
    "#secondary",
    # --- Social media and sharing features ---
    ".share",
    ".social",
    ".share-bar",
    ".social-links",
    ".follow",
    ".unfollow",
    # --- User comments and interaction areas ---
    ".comments",
    ".comment-respond",
    ".reply",
    "#comments",
    "#respond",
    # --- Metadata and auxiliary information ---
    ".meta",  # Often too broad, but can be useful
    ".post-meta",
    ".entry-meta",
    ".byline",
    ".timestamp",
    ".back-to-top",
    ".skip-link",
    ".conditions",
    ".terms",
    ".privacy",
    ".disclaimer",
    ".copyright",
    # --- Recommended and related content areas ---
    ".related",
    ".related-articles",
    ".related-posts",
    ".recommended",
    ".suggestions",
    ".top-stories",
    ".trending",
    ".popular-posts",
    # --- Form and user action elements ---
    ".button",  # Can be too broad
    ".btn",  # Can be too broad
    ".submit",
    ".search-form",
    ".subscribe",
    ".newsletter",
    ".signup",
    ".join-community",
    ".contribute",
    ".report",
    ".write-article",
    # --- Popups, overlays, and notifications ---
    ".popup",
    ".modal",
    ".overlay",
    ".cookie-notice",
    ".cookie-banner",
    ".gdpr-consent",
    # --- Hidden and auxiliary elements ---
    ".hidden",
    "[hidden]",
    ".screen-reader-text",
    # --- Miscellaneous, pagination, galleries ---
    ".pagination",
    ".gallery",
    ".author-box",
    ".print-link",
    ".edit-link",
    # --- Other general non-content prompts ---
    ".editor-choice",
    ".post-article",  # Often wraps the main content, be careful
    ".read-more",
    ".see-more",
    ".view-details",
    ".top",
    ".top-picks",
]


# --- Cleaning Function ---
def clean_html(
    html_content: str,
    base_url: str,  # Used for logging context
    exclude_tags: Optional[List[str]] = None,
    exclude_selectors: Optional[List[str]] = None,
) -> str:
    """
    Cleans HTML content by removing unwanted elements and returns the modified HTML string.

    This function uses BeautifulSoup to parse the HTML. It first attempts parsing
    with "lxml" and falls back to "html.parser" if lxml fails or is unavailable.
    Elements matching the `exclude_tags` list (by tag name) and elements
    matching the `exclude_selectors` list (by CSS selector) are decomposed
    from the HTML tree.

    Args:
        html_content (str): The raw HTML content string to be cleaned.
        base_url (str): The base URL of the webpage from which the HTML was
            obtained. Used primarily for logging purposes to provide context.
        exclude_tags (Optional[List[str]]): A list of HTML tag names to remove
            (e.g., ["script", "style"]). If None, `DEFAULT_EXCLUDE_TAGS` is used.
        exclude_selectors (Optional[List[str]]): A list of CSS selectors for
            elements to remove (e.g., [".ads", "#comments"]). If None,
            `DEFAULT_EXCLUDE_SELECTORS` is used.

    Returns:
        str: The cleaned HTML content as a string. If the initial parsing fails
             completely, an empty string is returned.

    Raises:
        None: Errors during parsing or element removal are logged as warnings/errors,
              and the function attempts to proceed or return an empty string.
              It does not explicitly raise exceptions for these operations.

    Side Effects:
        - Logs messages using the standard `logging` module, including:
            - Debug messages about the cleaning process and number of elements removed.
            - Error messages if HTML parsing fails.
            - Warning messages if finding specific tags/selectors fails.
        - Modifies the BeautifulSoup `soup` object in-place by decomposing elements.

    Examples:
        >>> sample_html = "<html><head><script>alert('bad')</script></head>"
        ...                 "<body><p>Good content</p><footer>Footer</footer></body></html>"
        >>> cleaned = clean_html(sample_html, "http://example.com")
        >>> "<script>" not in cleaned
        True
        >>> "<footer>" not in cleaned  # Assuming 'footer' is in DEFAULT_EXCLUDE_TAGS
        True
        >>> "<p>Good content</p>" in cleaned
        True

        >>> custom_exclusions_html = "<div><nav>Menu</nav><main>Main</main><span class='ad'>Ad</span></div>"
        >>> cleaned_custom = clean_html(
        ...     custom_exclusions_html,
        ...     "http://example.com/custom",
        ...     exclude_tags=["nav"],
        ...     exclude_selectors=[".ad"]
        ... )
        >>> "<nav>" not in cleaned_custom and "Ad</span>" not in cleaned_custom
        True
        >>> "<main>Main</main>" in cleaned_custom
        True
    """
    if not html_content:
        return ""

    # Use defaults if None is passed
    final_exclude_tags = (
        exclude_tags if exclude_tags is not None else DEFAULT_EXCLUDE_TAGS
    )
    final_exclude_selectors = (
        exclude_selectors
        if exclude_selectors is not None
        else DEFAULT_EXCLUDE_SELECTORS
    )

    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:  # Broad exception for parser initialization
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as parse_err:
            logger.error(f"Failed to parse HTML for {base_url}: {parse_err}")
            return ""  # Return empty string if parsing fails completely

    logger.debug(
        f"Cleaning HTML for {base_url} using {len(final_exclude_tags)} tag exclusions and {len(final_exclude_selectors)} selector exclusions."
    )

    elements_to_remove = []
    if final_exclude_tags:
        for tag_name in final_exclude_tags:
            try:
                elements_to_remove.extend(soup.find_all(tag_name))
            except (
                Exception
            ) as e:  # Catch potential errors from BeautifulSoup's find_all
                logger.warning(
                    f"Error finding exclude_tags '{tag_name}' for {base_url}: {e}"
                )

    if final_exclude_selectors:
        for selector in final_exclude_selectors:
            try:
                # BeautifulSoup's select can raise errors for invalid CSS selectors
                elements_to_remove.extend(soup.select(selector))
            except Exception as e:
                logger.warning(
                    f"Error processing exclude_selector '{selector}' for {base_url}: {e}"
                )

    removed_count = 0
    # Use set to avoid decomposing the same element multiple times if matched by different rules
    unique_elements = set(elements_to_remove)
    for element in unique_elements:
        if element.parent is not None:  # Ensure element is still in the tree
            element.decompose()
            removed_count += 1

    logger.debug(
        f"Removed {removed_count} elements based on exclusions for {base_url}."
    )

    return str(soup)


# --- Formatting Function ---
def format_html(
    cleaned_html: str,
    base_url: str,  # Used for logging context
    output_format: str = "markdown",
    markdownify_options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Formats a cleaned HTML string into the specified text format (Markdown or plain text).

    This function first parses the `cleaned_html` using BeautifulSoup (lxml with
    html.parser fallback). It then converts the parsed content.
    If `output_format` is "markdown", it uses the `markdownify` library.
    If `output_format` is "plain_text" (or any other value), it extracts
    text content using BeautifulSoup's `get_text()`.

    Args:
        cleaned_html (str): The HTML string to format, typically the output
            from `clean_html`.
        base_url (str): The base URL of the webpage, used for logging context.
        output_format (str): The desired output format. Expected values are
            "markdown" or "plain_text". Defaults to "markdown". If an
            unrecognized value is provided, it defaults to plain text extraction.
        markdownify_options (Optional[Dict[str, Any]]): A dictionary of options
            to pass to the `markdownify` function if `output_format` is "markdown".
            Refer to `markdownify` library documentation for available options.
            Example: `{'heading_style': 'atx'}`.

    Returns:
        str: The formatted text content. Returns an empty string if the input
             `cleaned_html` is empty, if parsing fails, or if an error occurs
             during formatting.

    Raises:
        None: Errors during parsing or formatting are logged, and the function
              attempts to return an empty string or fallback text extraction.

    Side Effects:
        - Logs messages using the standard `logging` module:
            - Debug messages about the formatting process.
            - Error messages if HTML parsing or final formatting fails.
            - Warning messages if no target element (body or root) is found.
        - Calls `markdownify.markdownify()` if `output_format` is "markdown", which
          is a CPU-bound operation.

    Examples:
        >>> html_for_md = "<p>Hello <b>world</b></p>"
        >>> md_output = format_html(html_for_md, "http://example.com", "markdown")
        >>> md_output
        'Hello **world**'

        >>> html_for_text = "<div><h1>Title</h1><p>Text here.</p></div>"
        >>> text_output = format_html(html_for_text, "http://example.com", "plain_text")
        >>> text_output
        'Title\\nText here.'

        >>> empty_html = ""
        >>> format_html(empty_html, "http://example.com")
        ''
    """
    if not cleaned_html:
        return ""

    try:
        soup = BeautifulSoup(cleaned_html, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(cleaned_html, "html.parser")
        except Exception as parse_err:
            logger.error(
                f"Failed to parse cleaned HTML for {base_url} during format: {parse_err}"
            )
            return ""

    formatted_content = ""
    try:
        # Prefer body, but fall back to the whole soup if body is not present
        target_element = soup.body or soup
        if not target_element:
            logger.warning(
                f"No target element (body or root) found for formatting {base_url}."
            )
            return ""  # Or consider soup.get_text() as a last resort?

        if output_format == "markdown":
            opts = markdownify_options or {}
            # Ensure target_element is converted to string for markdownify
            formatted_content = markdownify(str(target_element), **opts).strip()
            logger.debug(f"Formatted as Markdown for {base_url}")
        elif output_format == "plain_text":
            formatted_content = target_element.get_text(separator="\n", strip=True)
            logger.debug(f"Formatted as plain_text for {base_url}")
        else:
            logger.warning(
                f"Unknown output_format '{output_format}' for {base_url}. Defaulting to plain_text."
            )
            formatted_content = target_element.get_text(separator="\n", strip=True)

    except Exception as e:
        logger.error(
            f"Error during final formatting ({output_format}) for {base_url}: {e}"
        )
        # Fallback: attempt to extract all text from the original soup if formatting fails
        try:
            formatted_content = soup.get_text(separator="\n", strip=True)
            logger.info(
                f"Successfully fell back to full text extraction for {base_url} after formatting error."
            )
        except Exception as fallback_err:
            logger.error(
                f"Fallback text extraction also failed for {base_url}: {fallback_err}"
            )
            formatted_content = ""  # Ensure empty string on total failure
    return formatted_content


def clean_and_format_html(
    html_content: str,
    base_url: str,
    output_format: str = "markdown",
    exclude_tags: Optional[List[str]] = None,
    exclude_selectors: Optional[List[str]] = None,
    markdownify_options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Cleans HTML content then formats it to Markdown or plain text.

    This is a convenience function that first calls `clean_html` with the
    provided `html_content`, `base_url`, `exclude_tags`, and
    `exclude_selectors`. The resulting cleaned HTML is then passed to
    `format_html` with the `base_url`, `output_format`, and
    `markdownify_options`.

    Args:
        html_content (str): The raw HTML content string.
        base_url (str): The base URL of the webpage (for logging and context).
        output_format (str): Desired output format ("markdown" or "plain_text").
            Defaults to "markdown".
        exclude_tags (Optional[List[str]]): List of HTML tags to exclude during
            cleaning. Defaults to `DEFAULT_EXCLUDE_TAGS` if None.
        exclude_selectors (Optional[List[str]]): List of CSS selectors for elements
            to exclude during cleaning. Defaults to `DEFAULT_EXCLUDE_SELECTORS` if None.
        markdownify_options (Optional[Dict[str, Any]]): Options for the
            `markdownify` library if output is "markdown".

    Returns:
        str: The cleaned and formatted text content.

    Raises:
        None: Errors are handled and logged within the underlying `clean_html`
              and `format_html` functions.

    Side Effects:
        - Inherits all side effects (primarily logging) from `clean_html` and
          `format_html`.

    Examples:
        >>> raw_html = "<html><head><style>.hide{display:none}</style></head>"
        ...            "<body><p class='hide'>Hidden</p><h1>Title</h1>Content</body></html>"
        >>> result = clean_and_format_html(raw_html, "http://example.com", output_format="markdown")
        >>> "Hidden" not in result # Assuming '.hide' might be in default selectors or added
        True
        >>> result
        '# Title\\n\\nContent'

        >>> result_text = clean_and_format_html(raw_html, "http://example.com", output_format="plain_text")
        >>> result_text
        'Title\\nContent'
    """
    # Pass along None to let clean_html and format_html use their defaults
    cleaned_html = clean_html(
        html_content,
        base_url,
        exclude_tags=exclude_tags,  # Will use default if None
        exclude_selectors=exclude_selectors,  # Will use default if None
    )
    if not cleaned_html:  # If cleaning resulted in nothing, no point formatting
        return ""
    return format_html(
        cleaned_html,
        base_url,
        output_format=output_format,
        markdownify_options=markdownify_options,
    )


def extract_metadata_from_article_trafilatura(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """
    Extracts metadata from article HTML using the Trafilatura library.

    This function uses `trafilatura.bare_extraction` to get metadata fields.
    It attempts to extract title, URL, publication date, main text content,
    and a top image URL.

    Args:
        html_content (str): The raw HTML content of the article.
        base_url (str): The base URL of the webpage, passed to Trafilatura
            for context (e.g., resolving relative URLs, date extraction hints).

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing extracted metadata if
            successful and a `trafilatura.metadata.Document` object is returned.
            The dictionary structure is:
            {
                "title": Optional[str],       // Article title
                "url": Optional[str],         // Article URL (often from base_url or canonical)
                "date": Optional[str],        // Publication date as string (YYYY-MM-DD HH:MM:SS)
                "content": Optional[str],     // Main text content extracted by Trafilatura
                "top_image": Optional[str]    // URL of the main image, if found
            }
            Returns `None` if Trafilatura fails to extract a valid Document object
            or if `only_with_metadata=True` (default in this call) and no
            significant metadata is found.

    Raises:
        ImportError: If `trafilatura` library is not installed.
        Exception: Potentially, if `trafilatura.bare_extraction` encounters an
                   unexpected internal error, though it's designed to be robust.

    Side Effects:
        - Logs messages via Trafilatura's own logging if issues occur internally.
        - The `trafilatura.bare_extraction` call involves significant parsing and
          analysis of the HTML content.

    Examples:
        >>> # This is a conceptual example, actual HTML would be needed.
        >>> sample_article_html = "<html><head><title>Test Article</title></head>"
        ...                       "<body><p>This is the content.</p></body></html>"
        >>> metadata = extract_metadata_from_article_trafilatura(
        ...     sample_article_html, "http://example.com/article"
        ... )
        >>> if metadata:
        ...     print(metadata["title"]) # Expected: "Test Article" or similar
    """
    try:
        from trafilatura import bare_extraction
        from trafilatura.metadata import Document  # For type checking
    except ImportError:
        logger.error("Trafilatura library is not installed. Cannot extract metadata.")
        raise  # Re-raise for calling code to handle if critical

    document: Union[Document, Dict[str, Any], None] = None  # Initialize for clarity
    try:
        document = bare_extraction(
            filecontent=html_content,
            url=base_url,
            favor_recall=True,  # Option from Trafilatura, favors more content
            with_metadata=True,  # Essential to get metadata
            only_with_metadata=True,  # Returns None if no core metadata found
            include_images=True,  # To attempt image extraction
        )
    except Exception as e:
        logger.error(f"Trafilatura bare_extraction failed for {base_url}: {e}")
        return None  # Return None on unexpected trafilatura errors

    if not document or not isinstance(document, Document):
        logger.info(
            f"Trafilatura did not return a valid Document object for {base_url}."
        )
        return None

    # Trafilatura's Document object has attributes like .title, .url, .date, .raw_text, .image
    return {
        "title": document.title,
        "url": document.url,  # This might be the input base_url or a canonical URL
        "date": (
            str(document.date) if document.date else None
        ),  # Ensure string representation
        "content": document.raw_text,
        "top_image": (
            document.image if document.image else ""
        ),  # Default to empty string if no image
    }


def extract_metadata_from_article_newspaper4k(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """
    Extracts metadata from article HTML using the Newspaper4k library.

    This function initializes a Newspaper4k `Article` object, provides it with
    the pre-fetched `html_content`, and then parses it to extract metadata
    such as title, URL, publication date, main text, and images.

    Args:
        html_content (str): The raw HTML content of the article.
        base_url (str): The base URL of the webpage. This is provided to the
            `Article` constructor as its primary URL.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing extracted metadata if
            parsing is successful. The dictionary structure is:
            {
                "title": Optional[str],       // Article title
                "url": str,                   // Article URL (usually `base_url`)
                "date": Optional[datetime],   // Publication date (datetime object or None)
                "content": Optional[str],     // Main text content
                "top_image": Optional[str]    // URL of the top image, falling back to meta_img or first image
            }
            Returns `None` if Newspaper4k fails during download (loading HTML)
            or parsing, or if essential data cannot be extracted.

    Raises:
        ImportError: If `newspaper` library is not installed.
        newspaper.article.ArticleException: If methods like `parse()` are called
            in an incorrect sequence or if an article is not properly processed.
            This is caught internally and logged.

    Side Effects:
        - Logs messages using the standard `logging` module if errors occur.
        - The `article.download()` and `article.parse()` methods involve
          significant processing of the HTML content.

    Examples:
        >>> # Conceptual example, requires actual HTML.
        >>> article_html = "<html><title>News Story</title><body><p>Details...</p></body></html>"
        >>> metadata = extract_metadata_from_article_newspaper4k(
        ...     article_html, "http://news.example.com/story"
        ... )
        >>> if metadata:
        ...     print(metadata["title"]) # Expected: "News Story"
    """
    try:
        from newspaper import Article, ArticleException
    except ImportError:
        logger.error("Newspaper4k library is not installed. Cannot extract metadata.")
        raise  # Re-raise for calling code to handle

    article = Article(base_url)
    try:
        # Provide the already fetched HTML content to newspaper
        article.download(input_html=html_content)
        article.parse()
    except ArticleException as e:
        logger.error(
            f"Newspaper4k ArticleException for {base_url} during download/parse: {e}"
        )
        return None
    except Exception as e:  # Catch other potential errors during download/parse
        logger.error(
            f"Newspaper4k generic error for {base_url} during download/parse: {e}"
        )
        return None

    # Determine the best image URL
    image_url: Optional[str] = None
    if article.top_image:
        image_url = article.top_image
    elif article.meta_img:  # Fallback to meta_img
        image_url = article.meta_img
    elif (
        article.images and len(article.images) > 0
    ):  # Fallback to the first image in the list
        image_url = list(article.images)[0]  # article.images is a set
    else:
        image_url = ""  # Default to empty string if no image found

    # Ensure essential fields like title and text are present, otherwise it might not be a valid article
    if not article.title and not article.text:
        logger.warning(
            f"Newspaper4k extracted no title and no text for {base_url}. Considering it a failed extraction."
        )
        return None

    return {
        "title": article.title,
        "url": article.url,  # This is typically the base_url provided
        "date": article.publish_date,  # This is a datetime object or None
        "content": article.text,
        "top_image": image_url,
    }


def extract_metadata_combined_newspaper4k_trafilatura(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """
    Extracts metadata from article HTML using both Newspaper4k and Trafilatura,
    combining their results intelligently.

    It prioritizes valid (non-None and non-empty for strings, non-None for dates)
    results from Newspaper4k. For any metadata field not satisfactorily filled by
    Newspaper4k, it falls back to the corresponding field from Trafilatura.

    Args:
        html_content (str): The HTML content of the article.
        base_url (str): The base URL of the webpage, used by both extractors.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the combined metadata.
            The keys are "title", "url", "date", "content", "top_image".
            Values can be strings, datetime objects (for "date" from newspaper4k),
            or None if a valid value couldn't be found from either source for a
            particular field.
            Returns `None` if no useful metadata (all fields are None or invalid)
            could be extracted from either source.

    Raises:
        ImportError: If `newspaper` or `trafilatura` libraries are not installed
                     (propagated from the individual extraction functions).

    Side Effects:
        - Calls `extract_metadata_from_article_newspaper4k` and
          `extract_metadata_from_article_trafilatura`, inheriting their
          side effects (logging, CPU-intensive parsing).
        - Logs debug messages about which source was used for each metadata field.
        - Logs a warning if no valid metadata fields could be combined.

    Examples:
        >>> # Conceptual example
        >>> complex_html = "..." # HTML where one extractor might be better for some fields
        >>> combined_meta = extract_metadata_combined_newspaper4k_trafilatura(
        ...     complex_html, "http://example.com/complex-article"
        ... )
        >>> if combined_meta:
        ...     print(f"Title: {combined_meta.get('title')}")
        ...     print(f"Date from combined: {combined_meta.get('date')}")
    """

    # Get metadata from both sources
    # These functions handle their own internal errors and might return None
    # They also handle their own ImportError exceptions if libraries are missing.
    n4k_metadata = extract_metadata_from_article_newspaper4k(html_content, base_url)
    traf_metadata = extract_metadata_from_article_trafilatura(html_content, base_url)

    keys_to_extract = ["title", "url", "date", "content", "top_image"]

    # Initialize with None to ensure all keys are present in the output dictionary
    combined_metadata: Dict[str, Any] = {key: None for key in keys_to_extract}

    def is_value_valid(value: Any, key_name: str) -> bool:
        """
        Checks if a metadata value is considered valid.
        For strings ('title', 'url', 'content', 'top_image'), it must not be None
        or an empty/whitespace-only string.
        For 'date', it must not be None (can be datetime from n4k or str from traf).
        """
        if value is None:
            return False
        if key_name != "date" and isinstance(value, str) and not value.strip():
            return False
        # For date, just not being None is enough as it can be datetime or string
        return True

    for key in keys_to_extract:
        val_n4k = n4k_metadata.get(key) if n4k_metadata else None
        val_traf = traf_metadata.get(key) if traf_metadata else None

        if is_value_valid(val_n4k, key):
            combined_metadata[key] = val_n4k
            logger.debug(
                f"For {base_url}, using '{key}' from newspaper4k: {str(val_n4k)[:70]}..."
            )
        elif is_value_valid(val_traf, key):
            combined_metadata[key] = val_traf
            logger.debug(
                f"For {base_url}, using '{key}' from trafilatura (newspaper4k was invalid/None): {str(val_traf)[:70]}..."
            )
        else:
            logger.debug(
                f"For {base_url}, no valid value found for '{key}' from either source."
            )

    # If no valid data was extracted at all for any field by either method,
    # it might be appropriate to return None.
    if all(combined_metadata[key] is None for key in keys_to_extract):
        logger.warning(
            f"Could not extract any valid metadata fields for {base_url} from either source."
        )
        return None

    logger.info(f"Successfully combined metadata for {base_url}.")
    return combined_metadata
