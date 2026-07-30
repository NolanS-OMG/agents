import logging

from cryptography.fernet import Fernet

from src.app.core.config import settings

logger = logging.getLogger(__name__)


class CredentialVault:
    def __init__(self) -> None:
        if not settings.credential_encryption_key:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY not configured")
        try:
            self._fernet = Fernet(settings.credential_encryption_key.encode())
        except (ValueError, Exception) as e:
            raise RuntimeError(f"Invalid CREDENTIAL_ENCRYPTION_KEY format: {e}") from e

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self._fernet.decrypt(ciphertext.encode()).decode()


def get_vault() -> CredentialVault | None:
    if not settings.credential_encryption_key:
        logger.warning("CREDENTIAL_ENCRYPTION_KEY not set, vault disabled")
        return None
    return CredentialVault()
