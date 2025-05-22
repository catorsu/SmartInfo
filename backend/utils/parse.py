"""
Parse Utilities for the SmartInfo Backend.

This module provides helper functions for extracting and parsing structured data,
primarily JSON, from text strings.

Key Functions:
    - parse_json_from_text: Extracts and parses JSON content found within
      ```json ... ``` code blocks in a given text.
"""

import json
import re
from typing import (
    Any,
    Dict,
    List,
)  # List and Dict might still be used by callers expecting specific structures
import logging

logger = logging.getLogger(__name__)


def parse_json_from_text(text: str) -> Any:
    """
    Extracts and parses JSON content enclosed within ```json ... ``` markers from text.

    The function searches for a code block starting with ```json and ending with ```.
    The content within this block is then parsed as JSON.

    Args:
        text (str): The input text string that may contain a JSON code block.

    Returns:
        Any: The Python object parsed from the JSON content (e.g., a dictionary,
             list, string, number, boolean, or None).
             Returns an empty list (`[]`) if no JSON block is found, if the
             JSON content is empty after stripping, or if JSON parsing fails.
             Note: Returning an empty list for failure cases is a specific
             behavior of this function; standard `json.loads` would raise errors.

    Raises:
        None: `json.JSONDecodeError` and other exceptions during parsing are
              caught internally, logged as errors, and result in an empty list
              being returned. The function itself does not re-raise these exceptions.

    Side Effects:
        - Logs a warning if no JSON code block is found.
        - Logs an error if JSON decoding fails.
        - Logs an error for any other unexpected exception during parsing.

    Examples:
        >>> text_with_json_list = "Some text ```json\\n[{\"key\": \"value\"}, {\"id\": 1}]\\n``` more text."
        >>> parse_json_from_text(text_with_json_list)
        [{'key': 'value'}, {'id': 1}]

        >>> text_with_json_obj = "```json\\n{\"name\": \"Test\", \"valid\": true}\\n```"
        >>> parse_json_from_text(text_with_json_obj)
        {'name': 'Test', 'valid': True}

        >>> text_with_malformed_json = "```json\\n{\"key\": \"value\" \\n```" # Missing closing brace
        >>> parse_json_from_text(text_with_malformed_json) # Logs error, returns []
        []

        >>> text_without_json = "Just some regular text without a JSON block."
        >>> parse_json_from_text(text_without_json) # Logs warning, returns []
        []

        >>> text_with_empty_json_block = "```json\\n\\n```"
        >>> parse_json_from_text(text_with_empty_json_block) # Logs warning, returns []
        []
    """
    # Initialize variable for logging in case of early error before assignment
    json_text_for_error_log: str = ""
    try:
        # Regex to handle optional newline after ```json and before ```
        match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if not match:
            # Fallback for inline or non-standard spacing (e.g. ```json{"key":"value"}```)
            match = re.search(r"```json(.*?)```", text, re.DOTALL)

        if not match:
            logger.warning(
                "No JSON code block found in the provided text: %s",
                text[:100] + "..." if len(text) > 100 else text,
            )
            return []

        json_content_str = match.group(1).strip()
        # Assign to the error logging variable before json.loads might fail
        json_text_for_error_log = json_content_str

        if not json_content_str:
            logger.warning("Empty JSON content found within ```json ... ``` block.")
            return []  # json.loads('') would raise an error

        return json.loads(json_content_str)
    except json.JSONDecodeError as jde:
        logger.error(
            "JSON decoding failed for text: '%s'. Error: %s",
            (
                json_text_for_error_log[:100] + "..."
                if len(json_text_for_error_log) > 100
                else json_text_for_error_log
            ),
            jde,
        )
        return []
    except Exception as e:
        # Log the original text snippet for context if an unexpected error occurs
        logger.error(
            "Unexpected error while parsing JSON from text: %s. Error: %s",
            text[:200] + "..." if len(text) > 200 else text,
            e,
        )
        return []
