"""DB 密码对称加密（Fernet，key 来自 settings.secret_key）。"""
from __future__ import annotations

import base64
import hashlib

from metaprofile.shared.config.settings import settings


def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt_pw(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_pw(stored: str) -> str:
    # Fernet token 以 gAAAA 开头；否则视为历史明文直接返回
    if stored.startswith("gAAAA"):
        return _fernet().decrypt(stored.encode()).decode()
    return stored
