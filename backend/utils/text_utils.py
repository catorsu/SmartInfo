"""
Text utility functions for content processing and manipulation in the SmartInfo Backend.

This module currently provides functions for splitting text based on specific criteria.

Key Functions:
    - get_chunks: Splits text into a specified number of chunks based on the
                  distribution of Markdown-style links.
"""

from typing import List
import re


def get_chunks(text: str, num_chunks: int) -> List[str]:
    """
    Splits the input text into a specified number of chunks.

    The splitting strategy is based on distributing Markdown-style links
    (`[text](url)`) as evenly as possible among the chunks. Chunks are
    defined by the text segments surrounding these links.

    Args:
        text (str): The text to split into chunks.
        num_chunks (int): The desired number of chunks to create.
            If `num_chunks` is less than 1, the behavior might lead to
            the original text being returned as a single chunk (if links exist)
            or an empty list (if no links exist).

    Returns:
        List[str]: A list of text chunks.
            - If no Markdown links are found in `text`, returns an empty list.
            - If `num_chunks` is less than 1 and links exist, it typically
              returns a list containing the original text as a single chunk.
            - Otherwise, it returns a list of up to `num_chunks` strings,
              where each chunk contains a segment of the original text,
              with link distributions guiding the splits. Empty chunks (after
              stripping whitespace) are omitted.
            - If links exist but all resulting chunks are empty after stripping
              whitespace, it returns a list containing the original text.


    Raises:
        None: The function aims to handle various inputs gracefully without
              raising exceptions. Edge cases like `num_chunks <= 0` are
              managed internally.

    Side Effects:
        None.

    Examples:
        >>> text1 = "Part 1 [link1](url1). Part 2 [link2](url2). Part 3 [link3](url3). Part 4 [link4](url4)."
        >>> get_chunks(text1, 2)
        ['Part 1 [link1](url1). Part 2 [link2](url2). ', 'Part 3 [link3](url3). Part 4 [link4](url4).']

        >>> text2 = "No links here."
        >>> get_chunks(text2, 2)
        []

        >>> text3 = "[link1](url1)[link2](url2)[link3](url3)"
        >>> get_chunks(text3, 3)
        ['[link1](url1)', '[link2](url2)', '[link3](url3)']
        # Note: If num_chunks > total_pairs, it creates total_pairs chunks.
        >>> get_chunks(text3, 5)
        ['[link1](url1)', '[link2](url2)', '[link3](url3)']


        >>> text4 = "Only one [link](url) here."
        >>> get_chunks(text4, 3)
        ['Only one [link](url) here.']

        >>> text5 = "  [link1](url1)   [link2](url2)  " # Links separated by whitespace
        >>> get_chunks(text5, 2)
        ['  [link1](url1)   ', '[link2](url2)  ']

        >>> text_empty = ""
        >>> get_chunks(text_empty, 2)
        [] # Or could be [''] if input text itself is considered a chunk

        >>> text_with_links = "[a](1) [b](2)"
        >>> get_chunks(text_with_links, 0) # num_chunks <= 0
        ['[a](1) [b](2)']
        >>> get_chunks(text_with_links, -1)
        ['[a](1) [b](2)']

        >>> text_no_links_invalid_chunks = "No links"
        >>> get_chunks(text_no_links_invalid_chunks, 0)
        []
    """
    if not text:
        return []

    # Pattern to find Markdown links: [text](url)
    pattern = r"\[.*?\]\(.*?\)"  # Non-greedy match for text and URL parts
    matches = list(re.finditer(pattern, text))

    if not matches:
        # No links found, cannot split by link count.
        return []

    total_pairs = len(matches)

    # Handle num_chunks <= 0: effectively means "don't split" or "one chunk"
    if num_chunks <= 0:
        if text.strip():  # Return the original text if it's not just whitespace
            return [text]
        else:  # If original text is all whitespace, and no links to guide, return empty
            return []

    # Determine the number of links per chunk. Ensure at least 1.
    # If num_chunks is very large, pairs_per_chunk will be 1.
    pairs_per_chunk = max(1, total_pairs // num_chunks)
    chunks: List[str] = []

    # The actual number of chunks we can create is limited by total_pairs or num_chunks.
    # If num_chunks > total_pairs, we'll create total_pairs chunks, each "around" one link.
    actual_num_chunks = min(num_chunks, total_pairs)

    for i in range(actual_num_chunks):
        # Determine the start and end link indices for the current chunk
        start_pair_idx = i * pairs_per_chunk

        # For the last chunk, ensure it includes all remaining links
        if i == actual_num_chunks - 1:
            end_pair_idx = total_pairs  # Go up to (but not including) total_pairs index for matches list
        else:
            # Ensure end_pair_idx does not exceed total_pairs
            end_pair_idx = min((i + 1) * pairs_per_chunk, total_pairs)

        # This condition should ideally not be met if actual_num_chunks is derived correctly
        if start_pair_idx >= total_pairs:
            break  # Should not happen if loop is range(actual_num_chunks)

        # Determine character positions for slicing the text
        # Chunk starts at the beginning of its first link's match
        # (or text start if it's the very first chunk)
        if start_pair_idx == 0:
            start_pos = 0
        else:
            # Start the chunk from the beginning of the first link assigned to it.
            start_pos = matches[start_pair_idx].start()

        # Chunk ends at the beginning of the first link of the *next* chunk
        # (or text end if it's the last chunk or no more links for next chunk)
        if end_pair_idx >= total_pairs:
            end_pos = len(text)  # End of the entire text
        else:
            # End the chunk just before the start of the first link of the next chunk.
            end_pos = matches[end_pair_idx].start()

        chunk = text[start_pos:end_pos]
        if chunk.strip():  # Only add non-empty chunks
            chunks.append(chunk)

    # If links were present, but all resulting chunks were whitespace-only,
    # return the original text as a single chunk.
    if total_pairs > 0 and not chunks and text.strip():
        return [text]

    # If after all processing, chunks is empty (e.g. original text was whitespace, or only links that got filtered out somehow)
    # and the original text had no links (already handled), or had links but they resulted in empty chunks.
    # This path ensures that if we started with links, and ended with no chunks, we return empty.
    # The case of `total_pairs > 0 and not chunks and text.strip()` handles when original text was not empty.
    # If `text.strip()` is false, and `chunks` is empty, it will correctly return `chunks` (which is `[]`).

    return chunks
