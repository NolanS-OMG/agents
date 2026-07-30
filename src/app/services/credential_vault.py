import logging

from cryptography.fernet import Fernet

from src.app.core.config import settings

logger = logging.getLogger(__name__)


class CredentialVault:
    def __init__(self) -> None:
        if not settings.credential_encryption_key:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY not configured")
        self._fernet = Fernet(settings.credential_encryption_key.encode())

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
