"""
Security Utilities for SmartInfo Backend.

This module provides functions for password hashing and verification using bcrypt,
and for creating and decoding JWT (JSON Web Tokens) for user authentication
and session management.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

from jose import jwt, JWTError
import bcrypt

logger = logging.getLogger(__name__)


# It's crucial that SECRET_KEY is strong and kept secret.
# For production, this should be loaded from a secure environment variable.
SECRET_KEY: str = os.getenv(
    "SECRET_KEY", "a_very_insecure_default_secret_key_replace_me"
)
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 6000  # Token validity period in minutes.


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its bcrypt hashed version.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The bcrypt hashed password stored in the database.

    Returns:
        bool: True if the plain password matches the hashed password, False otherwise.
              Returns False also if `hashed_password` is not a valid bcrypt hash
              or if any other error occurs during comparison.

    Side Effects:
        - Logs a warning if `hashed_password` is invalid or if an unexpected
          error occurs during verification.
    """
    try:
        plain_password_bytes = plain_password.encode("utf-8")
        hashed_password_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except ValueError:
        # This can happen if hashed_password is not a valid bcrypt hash.
        logger.warning("Password verification failed: Invalid hashed password format.")
        return False
    except Exception as e:
        # Catch any other unexpected errors during bcrypt.checkpw.
        logger.warning(f"Password verification failed due to an unexpected error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hashes a plain password using bcrypt.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The bcrypt hashed password, decoded as a UTF-8 string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a JWT access token.

    The token includes the provided data in its payload and an expiration time.

    Args:
        data (Dict[str, Any]): The data payload to encode in the token (e.g.,
            `{"sub": user_id}`). The 'sub' (subject) claim is commonly used
            for the user identifier.
        expires_delta (Optional[timedelta]): A `timedelta` object specifying
            the token's lifespan. If None, the default duration specified by
            `ACCESS_TOKEN_EXPIRE_MINUTES` is used.

    Returns:
        str: The encoded JWT access token as a string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes a JWT access token and validates its signature and expiration.

    Args:
        token (str): The JWT token string to decode.

    Returns:
        Optional[Dict[str, Any]]: The decoded payload as a dictionary if the
            token is valid (correct signature, not expired, well-formed),
            otherwise None.

    Side Effects:
        - Logs a warning if token decoding fails due to `JWTError` (e.g.,
          signature mismatch, expired token, malformed token).
    """
    try:
        payload: Dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        # Log common JWT errors like ExpiredSignatureError, InvalidSignatureError, etc.
        logger.warning(f"JWT decoding/validation failed: {e}")
        return None
