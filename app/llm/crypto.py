import base64
import os

from app.core.errors import IntegrationNotInstalled


class LlmCredentialEncryptionError(RuntimeError):
    pass


def generate_encryption_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def _aesgcm(key_text: str):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise IntegrationNotInstalled(
            'Install LLM dependencies with pip install -e ".[llm]".'
        ) from exc

    if not key_text:
        raise LlmCredentialEncryptionError(
            "LLM credential encryption key is not configured."
        )

    try:
        key = base64.urlsafe_b64decode(key_text.encode("ascii"))
    except Exception as exc:
        raise LlmCredentialEncryptionError(
            "LLM credential encryption key is not valid base64."
        ) from exc

    if len(key) != 32:
        raise LlmCredentialEncryptionError(
            "LLM credential encryption key must decode to 32 bytes."
        )
    return AESGCM(key)


def encrypt_secret(secret: str, *, key_text: str) -> str:
    if not secret:
        raise ValueError("Secret cannot be empty.")
    aes = _aesgcm(key_text)
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, secret.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(ciphertext: str, *, key_text: str) -> str:
    aes = _aesgcm(key_text)
    try:
        payload = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        nonce, encrypted = payload[:12], payload[12:]
        return aes.decrypt(nonce, encrypted, None).decode("utf-8")
    except Exception as exc:
        raise LlmCredentialEncryptionError(
            "Could not decrypt LLM credential."
        ) from exc
