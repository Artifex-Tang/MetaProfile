from unittest.mock import patch

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn


def _conn(**kw) -> DBConnectionORM:
    base = dict(host="10.242.0.1", port=9030, database="ods_zbzx", username="gz_kt5",
                password_enc="gAAAA-secret", charset="utf8mb4")
    base.update(kw)
    orm = DBConnectionORM(name="x", dialect="doris", **base)
    return orm


def test_resolve_dsn_decrypts_password() -> None:
    with patch("metaprofile.ingest_ods.services.connections.decrypt_pw", return_value="DEC"):
        dsn = resolve_dsn(_conn())
    assert dsn == dict(host="10.242.0.1", port=9030, user="gz_kt5",
                       password="DEC", database="ods_zbzx", charset="utf8mb4",
                       connect_timeout=15, read_timeout=600)
