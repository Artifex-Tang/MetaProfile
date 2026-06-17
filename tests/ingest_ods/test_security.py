from metaprofile.ingest_ods.services.security import encrypt_pw, decrypt_pw


def test_encrypt_decrypt_roundtrip() -> None:
    pw = "92f5IRTld93lDPKYZZ5p"
    enc = encrypt_pw(pw)
    assert enc != pw
    assert decrypt_pw(enc) == pw


def test_decrypt_plaintext_fallback() -> None:
    # 兼容历史明文（未加密直接存）
    assert decrypt_pw("plain-password") == "plain-password"
