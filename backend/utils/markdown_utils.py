"""
Markdown processing utilities for the SmartInfo Backend.

This module provides a collection of utility functions to process and clean
Markdown text, primarily focusing on link manipulation.

Key Functions:
    - clean_markdown_links: Extracts, filters (using LINK_FILTER_REGEX and an
      optional exclusion list), and returns a string of specific Markdown links.
    - strip_image_links: Removes all Markdown image links (e.g., ![alt](src)).
    - strip_markdown_divider: Removes horizontal rule dividers.
    - strip_javascript_links: Removes "javascript:;" style links.
    - strip_extra_links_from_markdown: Extracts, filters (using an optional
      exclusion list), and returns a string of specific Markdown links.
    - strip_markdown_links: Removes all standard Markdown links (e.g., [text](url)),
      after first stripping image links.

The module defines `LINK_FILTER_REGEX` for sophisticated link filtering.
"""

import re
from urllib.parse import urljoin
from typing import List, Optional

# LINK_FILTER_REGEX: A compiled regular expression for identifying and filtering
# various types of undesirable or noisy Markdown links. This includes empty links,
# links with common non-content keywords (e.g., "Edit", "Login", "Download"),
# links with only numerical or symbolic text, links to common code repositories,
# tracking links, and links to common file extensions.
LINK_FILTER_REGEX = re.compile(
    r"""
    # ====================================================================
    # Rule Group 1: Structural & Empty Links
    # ====================================================================
    # 1.1: Empty title links: [ ](link)
    \[\s*\] \([^)]*\)

    # ====================================================================
    # Rule Group 2: Links Filtered by Specific Text Content (Keywords)
    # ====================================================================
    | \[\s* # Opening bracket and optional space
      (?:                             
          # Action/Button Keywords
          Edit|Delete|Reply|Comment|Share|Like|Download|View|Read\s*More|Source|Details|Info|Help|FAQ|Contact|Report|Flag
          |编辑|删除|回复|评论|分享|赞|喜欢|下载|查看|阅读更多|来源|详情|信息|帮助|常见问题|联系|举报
          # Navigation Keywords
          |Back|Next|Previous|Home|Index|Top|Jump\s*to|Skip\s*to
          |返回|下一步|下一页|上一步|上一页|首页|目录|回到顶部|跳转到
          # Placeholder Keywords
          |link|click\s*here|here|website|page|document
          |链接|这里|点击这里|网站|页面|文档
          # User Interaction Keywords
          |Login|Logout|Register|Sign\s*Up|Sign\s*In|Subscribe|Unsubscribe|Follow|Unfollow
          |登录|登出|退出|注册|订阅|取消订阅|关注|取消关注
          # E-commerce Keywords
          |Buy|Add\s*to\s*Cart|Checkout|Donate
          |购买|添加到购物车|结账|捐赠
          # Original User Keywords
          |收藏|更多
      )\
      \s* \d* \s* # Optional space, digits, space
      \] \([^)]*\)

    # ====================================================================
    # Rule Group 3: Links with Numerals/Symbols Only Titles
    # ====================================================================
    | \[\s* [\d#*+-]+ \s*\] \([^)]*\)

    # ====================================================================
    # Rule Group 4: Links Filtered by URL Patterns
    # ====================================================================

    # 4.1: Links to Code/Package/Download Sites URLs
    | \[[^\]]*\] \(\
        https?://(?:www\.)?\
        (?:                         # Domain list
            github\.com|gitlab\.com|bitbucket\.org|gitee\.com|\
            sourceforge\.net|launchpad\.net|code\.google\.com/archive|\
            npmjs\.com/package|pypi\.org/project|crates\.io/crates|\
            rubygems\.org/gems|search\.maven\.org/artifact|\
            hub\.docker\.com/(?:r|u)\
        )\
        /[^\s\)]+                    # Path part
      \)

    # 4.2: Links to Nav/Auth/Aggregate Page URLs
    | \[[^\]]*\] \(\
        https?://[^\s\)]+/         # Base URL + slash
        (?:                         # Path segments
            login|signup|register|auth|search|tags|categories|feeds\
        )\
        (?:/|$)                     # Followed by slash or end of path segment
        [^\s\)]* # Optional rest of URL
      \)

    # 4.3: Links with Tracking Parameters in URL
    | \[[^\]]*\] \(\
        https?://[^\s\)]+           # Base URL
        \?                          # Literal question mark for query string
        (?:                         # Non-capturing group for query params pattern
            [^)\s]* # Match any non-closing-paren/space chars before tracker
            \b(?:utm_[^=&]+|share=|tracking) # Look for tracking keys
            [^)&]* # Match remaining param value until & or ) (allow empty value)
        )\
        [^\s\)]* # Match the rest of the URL query string/fragment
      \)

    # 4.4: mailto: / tel: links
    | \[[^\]]*\] \(\
        (?:mailto|tel):[^\s\)]+     # mailto/tel scheme
      \)

    # ====================================================================
    # Rule Group 5: Links Filtered by Common Media/Document File Extensions in URL
    # ====================================================================
    | \[[^\]]*\] \(\
        [^\s\(\)]+                     # Main part of URL path (no spaces/parentheses)
        \.                             # Literal dot before extension
        (?:                            
            # Images
            jpg|jpeg|png|gif|bmp|webp|svg|tif|tiff|ico\
            # Audio
            |mp3|wav|ogg|aac|flac|m4a\
            # Video
            |mp4|mov|avi|wmv|mkv|webm|flv\
            # Documents
            |pdf|doc|docx|xls|xlsx|ppt|pptx\
            # Archives
            |zip|rar|gz|tar|bz2|7z\
        )\
        (?:[?#][^\s\)]*)?              # Optional query string or fragment
      \)
""",
    re.VERBOSE | re.IGNORECASE,
)


def clean_markdown_links(
    raw_text: str,
    exclude_urls: Optional[List[str]] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    """
    Extracts and filters Markdown links from text, returning only desired links.

    The function performs several steps:
    1. Removes image links (e.g., ![alt](src.jpg)).
    2. Applies `LINK_FILTER_REGEX` to remove common non-content links.
    3. Finds all remaining standard Markdown links ([text](url)).
    4. Converts relative URLs to absolute URLs using `base_url`.
    5. Filters out any links whose absolute URL is in `exclude_urls`.
    6. Returns a string of the remaining, valid Markdown links, each on a new line.
       If no links remain after filtering, returns `None`.

    Args:
        raw_text (str): The Markdown text to process.
        exclude_urls (Optional[List[str]]): A list of absolute URLs to exclude.
            If a link's resolved URL matches one in this list, it's removed.
            Defaults to None (no URL-based exclusion beyond `LINK_FILTER_REGEX`).
        base_url (Optional[str]): The base URL used to resolve relative link URLs
            found in `raw_text`. If None, relative links are kept as is.

    Returns:
        Optional[str]: A string containing the filtered Markdown links, each on a
                       new line (e.g., "[Link 1](url1)\\n[Link 2](url2)").
                       Returns `None` if `raw_text` is empty, or if no links
                       remain after all filtering steps.

    Raises:
        None: This function is designed to handle errors internally and
              return `None` or an empty string rather than raising exceptions.

    Side Effects:
        None.

    Examples:
        >>> text = "Some text with ![image](img.png) and [Good Link](page.html). "
        ...        "Also [Empty Title]() and [Edit](edit.php). "
        ...        "Exclude [This One](http://example.com/exclude_me)."
        >>> clean_markdown_links(text, exclude_urls=["http://example.com/exclude_me"], base_url="http://example.com/")
        '[Good Link](http://example.com/page.html)'

        >>> text2 = "No valid links here: [ ](empty.html)"
        >>> clean_markdown_links(text2, base_url="http://example.com/")
        None

        >>> text3 = "[Relative Link](/path/to/file)"
        >>> clean_markdown_links(text3, base_url="http://mysite.com")
        '[Relative Link](http://mysite.com/path/to/file)'
    """
    if not raw_text:
        return ""  # Return empty string for empty input, consistent with other strip functions

    text_without_images = strip_image_links(raw_text)
    if not text_without_images:  # If stripping images results in empty, return early
        return None

    # Apply the comprehensive link filter regex
    text_filtered_by_regex = LINK_FILTER_REGEX.sub("", text_without_images)
    if (
        not text_filtered_by_regex.strip()
    ):  # Check if anything remains after regex filtering
        return None

    # Find all remaining standard Markdown links: [text](url)
    link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"  # More specific: non-empty text
    extracted_links = re.findall(link_pattern, text_filtered_by_regex)

    if not extracted_links:
        return None

    final_links_to_keep = []
    for text, url in extracted_links:
        # Resolve relative URLs to absolute ones if base_url is provided
        full_url = urljoin(base_url, url) if base_url else url

        # Apply exclusion list if provided
        if exclude_urls and full_url in exclude_urls:
            continue  # Skip this link if it's in the exclusion list

        final_links_to_keep.append(f"[{text.strip()}]({full_url})")

    if final_links_to_keep:
        return "\n".join(final_links_to_keep)
    else:
        return None


def strip_image_links(raw_text: str) -> str:
    """
    Removes Markdown image links (e.g., ![alt text](image.png)) from text.

    Args:
        raw_text (str): The Markdown text.

    Returns:
        str: The text with image links removed. Returns an empty string if
             the input `raw_text` is empty.

    Raises:
        None.

    Side Effects:
        None.

    Examples:
        >>> strip_image_links("Hello ![World](world.png) this is text.")
        'Hello  this is text.'
        >>> strip_image_links("![caption](img.jpg)")
        ''
        >>> strip_image_links("No images here.")
        'No images here.'
    """
    if not raw_text:
        return ""
    # Regex for ![alt text](url)
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw_text)


def strip_markdown_divider(raw_text: str) -> str:
    """
    Removes Markdown horizontal rule dividers (e.g., ---, ***, ___).

    Args:
        raw_text (str): The Markdown text.

    Returns:
        str: The text with dividers removed. Returns an empty string if
             the input `raw_text` is empty.

    Raises:
        None.

    Side Effects:
        None.

    Examples:
        >>> strip_markdown_divider("Text above\\n***\\nText below")
        'Text above\\n\\nText below'
        >>> strip_markdown_divider("Hello\\n---")
        'Hello\\n'
        >>> strip_markdown_divider("No dividers.")
        'No dividers.'
    """
    if not raw_text:
        return ""
    # Regex for lines consisting only of 3 or more hyphens, asterisks, or underscores,
    # potentially surrounded by whitespace.
    return re.sub(r"^\s*([-*_]\s*){3,}\s*$", "", raw_text, flags=re.MULTILINE)


def strip_javascript_links(raw_text: str) -> str:
    """
    Removes "javascript:;" style Markdown links (e.g., [text](javascript:;)).

    Args:
        raw_text (str): The Markdown text.

    Returns:
        str: The text with "javascript:;" links removed. Returns an empty
             string if the input `raw_text` is empty.

    Raises:
        None.

    Side Effects:
        None.

    Examples:
        >>> strip_javascript_links("Click [here](javascript:;) for nothing.")
        'Click  for nothing.'
        >>> strip_javascript_links("[Link](http://example.com) [JS Link](javascript:;)")
        '[Link](http://example.com) '
    """
    if not raw_text:
        return ""
    # Regex for [any text](javascript:;)
    return re.sub(r"\[[^\]]*\]\(javascript:;\)", "", raw_text)


def strip_extra_links_from_markdown(
    raw_text: str,
    exclude_urls: Optional[List[str]] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    """
    Extracts and filters Markdown links, excluding specified URLs.

    This function is similar to `clean_markdown_links` but does *not* apply
    the `LINK_FILTER_REGEX`. It directly finds all standard Markdown links,
    resolves their URLs, filters them against `exclude_urls`, and returns
    a newline-separated string of the remaining links.

    Args:
        raw_text (str): The Markdown text to process.
        exclude_urls (Optional[List[str]]): A list of absolute URLs to exclude.
            If a link's resolved URL matches one in this list, it's removed.
            Defaults to None (no URL-based exclusion).
        base_url (Optional[str]): The base URL used to resolve relative link URLs.
            If None, relative links are kept as is.

    Returns:
        Optional[str]: A string containing the filtered Markdown links, each on a
                       new line. Returns `None` if `raw_text` is empty or if no
                       links remain after filtering.

    Raises:
        None.

    Side Effects:
        None.

    Examples:
        >>> text = "[Keep This](page1.html) and [Remove This](http://example.com/remove)"
        >>> strip_extra_links_from_markdown(
        ...     text,
        ...     exclude_urls=["http://example.com/remove"],
        ...     base_url="http://example.com/"
        ... )
        '[Keep This](http://example.com/page1.html)'

        >>> text2 = "Only [Good Link](good.html)"
        >>> strip_extra_links_from_markdown(text2, base_url="http://site.com/")
        '[Good Link](http://site.com/good.html)'
    """
    if not raw_text:  # Check if raw_text itself is empty
        return None  # Return None for empty input to align with clean_markdown_links

    # Extract all standard Markdown links: [text](url)
    link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    extracted_links = re.findall(link_pattern, raw_text)

    if not extracted_links:
        return None

    filtered_links_to_keep = []
    for text, url in extracted_links:
        full_url = urljoin(base_url, url) if base_url else url

        if exclude_urls and full_url in exclude_urls:
            continue  # Skip if in exclusion list

        filtered_links_to_keep.append(f"[{text.strip()}]({full_url})")

    if filtered_links_to_keep:
        return "\n".join(filtered_links_to_keep)
    else:
        return None


def strip_markdown_links(raw_text: str) -> str:
    """
    Removes all standard Markdown links ([text](url)) from text, after stripping image links.

    Args:
        raw_text (str): The Markdown text.

    Returns:
        str: The text with standard Markdown links removed. Returns an empty
             string if the input `raw_text` is empty.

    Raises:
        None.

    Side Effects:
        None.

    Examples:
        >>> strip_markdown_links("Hello [World](world.html) and ![Image](img.png).")
        'Hello  and .'
        >>> strip_markdown_links("Just text.")
        'Just text.'
    """
    if not raw_text:
        return ""

    # First, remove image links, as they also match the general link pattern
    # but have a leading '!'
    text_without_images = strip_image_links(raw_text)

    if not text_without_images:  # If only images were present
        return ""

    # Then, remove standard Markdown links: [text](url)
    return re.sub(r"\[[^\]]*\]\([^)]*\)", "", text_without_images)
