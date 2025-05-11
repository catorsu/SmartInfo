"""
Text utility functions for content processing and manipulation
"""

from typing import List
import re


def get_chunks(text: str, num_chunks: int) -> List[str]:
    """
    Split the input text into roughly equal-sized chunks by []() pair count.

    Args:
        text: The text to split into chunks
        num_chunks: The number of chunks to create

    Returns:
        A list of text chunks as strings
    """

    pattern = r"\[.*?\]\(.*?\)"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return []

    total_pairs = len(matches)

    pairs_per_chunk = max(1, total_pairs // num_chunks)
    chunks: List[str] = []

    actual_num_chunks = min(num_chunks, total_pairs)

    for i in range(actual_num_chunks):
        start_pair_idx = i * pairs_per_chunk

        # For the last chunk, include all remaining pairs
        if i == actual_num_chunks - 1:
            end_pair_idx = total_pairs
        else:
            end_pair_idx = min((i + 1) * pairs_per_chunk, total_pairs)

        if start_pair_idx >= total_pairs:
            break

        if start_pair_idx == 0:
            start_pos = 0
        else:

            start_pos = matches[start_pair_idx].start()

        if end_pair_idx >= total_pairs:
            end_pos = len(text)
        else:

            end_pos = matches[end_pair_idx].start()

        chunk = text[start_pos:end_pos]
        if chunk.strip():
            chunks.append(chunk)

    # Special case: if we have pairs but didn't create any chunks, return the whole text
    if total_pairs > 0 and not chunks:
        return [text]

    return chunks
