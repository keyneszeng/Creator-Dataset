import hashlib
import secrets


def generate_api_key() -> tuple[str, str, str]:
    secret = "cd_" + secrets.token_urlsafe(32)
    prefix = secret[:12]
    digest = hash_api_key(secret)
    return secret, prefix, digest


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
