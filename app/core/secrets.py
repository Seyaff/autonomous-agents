"""
Encryption for secrets the database holds, such as a restaurant's WhatsApp token.

Values are stored as "enc:v1:<token>". Anything without that prefix is read as
plain text, so tokens saved before encryption existed still work until they're
reconnected.

The key is TOKEN_ENCRYPTION_KEY, a Fernet key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from core.settings import settings

logger = logging.getLogger(__name__)

PREFIX = "enc:v1:"


class SecretError(Exception):
    pass


def _fernet() -> Optional[Fernet]:
    key = (settings.TOKEN_ENCRYPTION_KEY or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except ValueError as e:
        raise SecretError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from e


def protect(value: Optional[str]) -> Optional[str]:
    """Encrypts a secret for storage. Without a key this stores it as it is and logs a warning,
    so local development still works. Production must set the key."""
    if not value:
        return value
    fernet = _fernet()
    if fernet is None:
        logger.warning("TOKEN_ENCRYPTION_KEY is not set: a WhatsApp token is being stored unencrypted")
        return value
    return PREFIX + fernet.encrypt(value.encode()).decode()


def reveal(value: Optional[str]) -> Optional[str]:
    """Returns the plain secret for use. Raises SecretError if it can't be decrypted."""
    if not value or not value.startswith(PREFIX):
        return value
    fernet = _fernet()
    if fernet is None:
        raise SecretError("This token is encrypted but TOKEN_ENCRYPTION_KEY is not set")
    try:
        return fernet.decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as e:
        raise SecretError("Could not decrypt the stored token. The encryption key may have changed.") from e
