"""
HTML Utils for cleaning and formatting HTML content.
"""

import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from markdownify import markdownify

logger = logging.getLogger(__name__)

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
    "img",
    "picture",
    "svg",
    "figure",
    "figcaption",
]


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
    ".meta",
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
    ".button",
    ".btn",
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
    ".post-article",
    ".read-more",
    ".see-more",
    ".view-details",
    ".top",
    ".top-picks",
]


# --- Cleaning Function ---
def clean_html(
    html_content: str,
    base_url: str,
    exclude_tags: Optional[List[str]] = DEFAULT_EXCLUDE_TAGS,
    exclude_selectors: Optional[List[str]] = DEFAULT_EXCLUDE_SELECTORS,
) -> str:
    """
    Clean HTML content, remove unwanted elements, and return the cleaned HTML string.

    Args:
        html_content: Original HTML content
        base_url: Base URL of the webpage (for logging)
        exclude_tags: List of HTML tags to exclude
        exclude_selectors: List of CSS selectors to exclude

    Returns:
        Cleaned HTML string
    """
    if not html_content:
        return ""

    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as parse_err:
            logger.error(f"Failed to parse HTML for {base_url}: {parse_err}")
            return ""  # Return empty string if parsing fails completely

    logger.debug(f"Cleaning HTML for {base_url}.")

    # --- Initial cleaning ---
    elements_to_remove = []
    if exclude_tags:
        for tag_name in exclude_tags:
            try:
                elements_to_remove.extend(soup.find_all(tag_name))
            except Exception as e:
                logger.warning(f"Error finding exclude_tags '{tag_name}': {e}")

    if exclude_selectors:
        for selector in exclude_selectors:
            try:
                elements_to_remove.extend(soup.select(selector))
            except Exception as e:
                logger.warning(f"Error processing exclude_selector '{selector}': {e}")

    removed_count = 0
    unique_elements = set(elements_to_remove)
    for element in unique_elements:
        if element.parent is not None:
            element.decompose()
            removed_count += 1

    logger.debug(
        f"Removed {removed_count} elements based on exclusions for {base_url}."
    )

    return str(soup)


# --- Formatting Function ---
def format_html(
    cleaned_html: str,
    base_url: str,
    output_format: str = "markdown",
    markdownify_options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Format the cleaned HTML string into the specified text format.

    Args:
        cleaned_html: HTML string returned by clean_html
        base_url: Base URL of the webpage (for logging)
        output_format: Output format, 'markdown' or 'plain_text'
        markdownify_options: Additional options passed to markdownify

    Returns:
        Formatted text content
    """
    if not cleaned_html:
        return ""

    try:
        soup = BeautifulSoup(cleaned_html, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(cleaned_html, "html.parser")
        except Exception as parse_err:
            logger.error(f"Failed to parse cleaned HTML for {base_url}: {parse_err}")
            return ""
    formatted_content = ""
    try:
        target_element = soup.body or soup
        if not target_element:
            logger.warning(f"No target element (body or root) found for {base_url}.")
            return ""
        if output_format == "markdown":
            opts = markdownify_options or {}
            formatted_content = markdownify(str(target_element), **opts).strip()
            logger.debug(f"Formatted as Markdown for {base_url}")
        else:
            formatted_content = target_element.get_text(separator="\n", strip=True)
            logger.debug(f"Formatted as plain_text for {base_url}")
    except Exception as e:
        logger.error(
            f"Error during final formatting ({output_format}) for {base_url}: {e}"
        )
        # Fallback: directly extract all text
        try:
            formatted_content = soup.get_text(separator="\n", strip=True)
        except Exception:
            formatted_content = ""
    return formatted_content


def clean_and_format_html(
    html_content: str,
    base_url: str,
    output_format: str = "markdown",
    exclude_tags: Optional[List[str]] = DEFAULT_EXCLUDE_TAGS,
    exclude_selectors: Optional[List[str]] = DEFAULT_EXCLUDE_SELECTORS,
    markdownify_options: Optional[Dict[str, Any]] = None,
) -> str:
    """Removes elements and formats the remaining HTML."""
    cleaned_html = clean_html(html_content, base_url, exclude_tags, exclude_selectors)
    return format_html(cleaned_html, base_url, output_format, markdownify_options)


def extract_metadata_from_article_trafilatura(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """Extract metadata from article html."""
    from trafilatura import bare_extraction
    from trafilatura.metadata import Document

    document = bare_extraction(
        html_content,
        url=base_url,
        favor_recall=True,
        with_metadata=True,
        only_with_metadata=True,
        include_images=True,
    )
    if not document or not isinstance(document, Document):
        return None

    return {
        "title": document.title,
        "url": document.url,
        "date": document.date,
        "content": document.raw_text,
        "top_image": document.image if document.image else "",
    }


def extract_metadata_from_article_newspaper4k(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """Extract metadata from article html using newspaper4k."""
    from newspaper import Article

    article = Article(base_url)
    article.download(html_content)
    article.parse()
    image_url = None
    if article.top_image:
        image_url = article.top_image
    else:
        if article.meta_img:
            image_url = article.meta_img
        else:
            if article.images:
                image_url = article.images[0]
            else:
                image_url = ""

    return {
        "title": article.title,
        "url": article.url,
        "date": article.publish_date,
        "content": article.text,
        "top_image": image_url,
    }


def extract_metadata_combined_newspaper4k_trafilatura(
    html_content: str, base_url: str
) -> Optional[Dict[str, Any]]:
    """
    Extracts metadata from article HTML using both newspaper4k and trafilatura,
    combining their results.

    It prioritizes valid (non-None and non-empty for strings) results from
    newspaper4k, then falls back to trafilatura for any fields not
    satisfactorily filled by newspaper4k.

    Args:
        html_content: The HTML content of the article.
        base_url: The base URL of the webpage.

    Returns:
        A dictionary containing the combined metadata (title, url, date,
        content, image), or None if no useful metadata could be extracted
        from either source.
    """

    # Get metadata from both sources
    # These functions already handle their own internal errors and might return None
    n4k_metadata = extract_metadata_from_article_newspaper4k(html_content, base_url)
    traf_metadata = extract_metadata_from_article_trafilatura(html_content, base_url)

    keys_to_extract = ["title", "url", "date", "content", "top_image"]

    # Initialize with None to ensure all keys are present in the output dictionary
    combined_metadata: Dict[str, Any] = {key: None for key in keys_to_extract}

    def is_value_valid(value: Any) -> bool:
        """
        Checks if a metadata value is considered valid.
        For strings, it must not be None or an empty/whitespace-only string.
        For other types (like datetime for 'date'), it must not be None.
        """
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return True

    for key in keys_to_extract:
        val_n4k = n4k_metadata.get(key) if n4k_metadata else None
        val_traf = traf_metadata.get(key) if traf_metadata else None

        if is_value_valid(val_n4k):
            combined_metadata[key] = val_n4k
            logger.debug(
                f"For {base_url}, using '{key}' from newspaper4k: {str(val_n4k)[:50]}..."
            )
        elif is_value_valid(val_traf):
            combined_metadata[key] = val_traf
            logger.debug(
                f"For {base_url}, using '{key}' from trafilatura (newspaper4k was invalid/None): {str(val_traf)[:50]}..."
            )
        else:
            logger.debug(
                f"For {base_url}, no valid value found for '{key}' from either source."
            )

    # If no valid data was extracted at all from any field by either method,
    # it might be appropriate to return None, consistent with the individual functions.
    if all(value is None for value in combined_metadata.values()):
        logger.warning(
            f"Could not extract any valid metadata fields for {base_url} from either source."
        )
        return None

    logger.info(f"Successfully combined metadata for {base_url}.")
    return combined_metadata
