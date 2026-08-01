"""Encrypted RFC 6238 TOTP support for account MFA."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import settings


TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6


class MfaError(ValueError):
    """A safe MFA configuration or verification error."""


class MfaService:
    @staticmethod
    def create_secret() -> str:
        return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

    @classmethod
    def encrypt_secret(cls, secret: str) -> str:
        return cls._fernet().encrypt(secret.encode("ascii")).decode("ascii")

    @classmethod
    def verify_encrypted_secret(cls, encrypted_secret: str | None, code: str | None) -> bool:
        if not encrypted_secret or not isinstance(code, str) or not code.isascii() or not code.isdigit():
            return False
        if len(code) != TOTP_DIGITS:
            return False
        try:
            secret = cls._fernet().decrypt(encrypted_secret.encode("ascii"), ttl=None).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            return False
        return any(hmac.compare_digest(cls._totp(secret, offset), code) for offset in (-1, 0, 1))

    @staticmethod
    def provisioning_uri(secret: str, username: str) -> str:
        issuer = settings.app_name
        label = quote(f"{issuer}:{username}", safe="")
        return (
            f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}&algorithm=SHA1"
            f"&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
        )

    @staticmethod
    def _totp(secret: str, offset: int) -> str:
        padding = "=" * (-len(secret) % 8)
        key = base64.b32decode(secret + padding, casefold=True)
        counter = int(time.time() // TOTP_PERIOD_SECONDS) + offset
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        start = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[start : start + 4])[0] & 0x7FFF_FFFF) % (10**TOTP_DIGITS)
        return f"{value:0{TOTP_DIGITS}d}"

    @staticmethod
    def _fernet() -> Fernet:
        if not settings.auth_mfa_encryption_key:
            raise MfaError("MFA is not configured on this server")
        try:
            return Fernet(settings.auth_mfa_encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise MfaError("AUTH_MFA_ENCRYPTION_KEY is invalid") from error
