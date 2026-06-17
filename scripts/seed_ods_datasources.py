"""幂等种子：db_connections(云+本地 Doris) + data_source_configs(两条 sql_warehouse 源)。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.security import encrypt_pw
from metaprofile.settings_api.domain.orm_models import DataSourceConfigORM

_CLOUD = dict(name="ods-cloud-doris", dialect="doris", host="10.242.0.1", port=9030,
              database="ods_zbzx", username="gz_kt5")
_LOCAL = dict(name="ods-local-doris", dialect="doris", host="127.0.0.1", port=9030,
              database="ods_zbzx", username="root")

_LOCAL_CFG = {
    "db_connection_id": None,  # 运行时回填
    "table_set": ["ods_company_basic_info", "ods_invention_patent_cn",
                  "ods_science_literature", "ods_market_analysis_cn",
                  "ods_talent_info_cn", "ods_strategic_policy_cn",
                  "ods_industry_report_cn", "ods_key_events_cn"],
    "profile_types": ["all"], "mode": "both", "enable_relations": True,
    "watermark_col": "update_time", "batch_size": 1000, "workers": 8,
}
_CLOUD_CFG = {**_LOCAL_CFG, "mode": "structured_only"}


async def _upsert_conn(session: AsyncSession, spec: dict, pw_plain: str) -> DBConnectionORM:
    orm = (await session.execute(
        select(DBConnectionORM).where(DBConnectionORM.name == spec["name"])
    )).scalars().first()
    if orm is None:
        orm = DBConnectionORM(**spec, password_enc=encrypt_pw(pw_plain))
        session.add(orm)
    return orm


async def seed(session: AsyncSession, *, cloud_pw: str, local_pw: str, secret: str) -> None:
    cloud = await _upsert_conn(session, _CLOUD, cloud_pw)
    local = await _upsert_conn(session, _LOCAL, local_pw)
    await session.flush()

    for name, cfg, cron in (
        ("ODS-本地-Doris", {**_LOCAL_CFG, "db_connection_id": local.id}, "0 2 * * *"),
        ("ODS-云-Doris", {**_CLOUD_CFG, "db_connection_id": cloud.id}, None),
    ):
        existing = (await session.execute(
            select(DataSourceConfigORM).where(DataSourceConfigORM.name == name)
        )).scalars().first()
        if existing is None:
            session.add(DataSourceConfigORM(
                name=name, source_type="sql_warehouse", profile_type="all",
                config_json=cfg, schedule_cron=cron, is_enabled=True,
            ))
    await session.commit()


if __name__ == "__main__":
    import asyncio
    from metaprofile.shared.db.postgres import get_session

    async def main() -> None:
        import os
        async with get_session() as s:
            await seed(s, cloud_pw=os.environ["ODS_CLOUD_PW"],
                       local_pw=os.environ.get("ODS_LOCAL_PW", ""),
                       secret=os.environ.get("SECRET_KEY", "dev"))
    asyncio.run(main())
