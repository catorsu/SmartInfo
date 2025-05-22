"""
Token Utilities for the SmartInfo Backend.

This module provides functions for calculating the token size of text,
primarily using the `deepseek-tokenizer`. The tokenizer is an optional
dependency; if not installed, token calculation for relevant models will default
to returning 0 and log a warning.

Key Functions:
    - get_token_size: Calculates the token count of a given text string using
      a specified tokenizer (currently supports "deepseek").
"""

import logging

logger = logging.getLogger(__name__)

# Attempt to import the deepseek tokenizer.
# This is an optional dependency. If not installed, tokenization for
# deepseek models will not be available.
# Installation: pip install deepseek-tokenizer
try:
    from deepseek_tokenizer import ds_token
except ImportError:
    ds_token = None  # Explicitly set to None if import fails
    logger.warning(
        "deepseek-tokenizer not installed. Token size calculation for 'deepseek' "
        "models will not be available. Please run: pip install deepseek-tokenizer"
    )


def get_token_size(text: str, model_type: str = "deepseek") -> int:
    """
    Calculates the token size of the given text using the specified tokenizer.

    Currently, this function primarily supports the 'deepseek' model type,
    relying on the `deepseek-tokenizer` library. If the tokenizer for the
    specified `model_type` is not supported or if the necessary library is
    not installed, the function will log a warning and return 0.

    Args:
        text (str): The text for which to calculate the token size.
        model_type (str): The type of model tokenizer to use.
            Currently, only "deepseek" is actively supported.
            Defaults to "deepseek".

    Returns:
        int: The estimated token size of the text. Returns 0 if the
             `model_type` is unsupported, the required tokenizer library
             is not available, or if an error occurs during tokenization.

    Raises:
        None: Exceptions during the tokenization process are caught internally,
              logged as warnings, and result in a return value of 0.

    Side Effects:
        - Logs a warning if the `deepseek-tokenizer` is not installed when
          `model_type` is "deepseek".
        - Logs a warning if an unsupported `model_type` is specified.
        - Logs a warning if the tokenizer fails to encode the text.

    Examples:
        >>> # Assuming deepseek-tokenizer is installed
        >>> get_token_size("Hello world!") # model_type defaults to "deepseek"
        # Expected: (an integer, e.g., 2 or 3 depending on the tokenizer)
        # Example output: 3 (if "Hello", " world", "!" are tokens)

        >>> get_token_size("こんにちは世界", model_type="deepseek")
        # Expected: (an integer representing token count for Japanese text)

        >>> get_token_size("Some text", model_type="unsupported_type")
        # Logs: "Tokenizer for model type 'unsupported_type' is not supported. Returning 0."
        # Returns: 0

        >>> # If deepseek-tokenizer is not installed:
        >>> # get_token_size("Test text")
        # Logs: "Deepseek tokenizer is not available. Cannot calculate token size."
        # Returns: 0
    """

    if model_type == "deepseek":
        if ds_token:  # Check if the tokenizer object was successfully imported
            try:
                # The encode method returns a list of token IDs
                return len(ds_token.encode(text))
            except Exception as e:
                logger.warning(
                    f"Deepseek tokenizer failed for text starting with '{text[:50]}...': {e}. "
                    "Returning 0 tokens."
                )
                return 0
        else:
            # This case is hit if `ds_token` is None due to ImportError
            logger.warning(
                "Deepseek tokenizer is not available (likely not installed). "
                "Cannot calculate token size for 'deepseek' model. Returning 0."
            )
            return 0
    else:
        logger.warning(
            f"Tokenizer for model type '{model_type}' is not currently supported. "
            "Returning 0 tokens."
        )
        return 0
