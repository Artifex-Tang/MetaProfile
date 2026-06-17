"""DBConnectionORM → pymysql 连接参数。"""
from __future__ import annotations

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.security import decrypt_pw


def resolve_dsn(conn: DBConnectionORM) -> dict:
    return {
        "host": conn.host,
        "port": conn.port,
        "user": conn.username,
        "password": decrypt_pw(conn.password_enc),
        "database": conn.database,
        "charset": conn.charset or "utf8mb4",
        "connect_timeout": 15,
        "read_timeout": 600,
    }
