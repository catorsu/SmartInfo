"""
Parse Utils for parsing JSON from text.
"""

import json
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def parse_json_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract and parse JSON content enclosed within ```json ... ``` markers.

    Args:
        text: The input text that may contain a JSON code block.

    Returns:
        A list of dictionaries parsed from the JSON content.
        Returns an empty list if no JSON block is found or parsing fails.
    """
    try:
        match = re.search(r"```json(.*?)```", text, re.DOTALL)
        if not match:
            logger.warning("No JSON code block found in the provided text.")
            return []

        json_text = match.group(1).strip()

        return json.loads(json_text)
    except json.JSONDecodeError as jde:
        logger.error("JSON decoding failed: %s", jde)
        return []
    except Exception as e:
        logger.error("Unexpected error while parsing JSON from text: %s", e)
        return []
