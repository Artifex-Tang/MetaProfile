"""数据采集服务：读取数据源配置 → 拉取数据 → 字段映射 → 调画像API导入。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import IngestErrorORM, IngestRawORM
from metaprofile.settings_api.domain.orm_models import CollectionTaskORM, DataSourceConfigORM
from metaprofile.settings_api.schemas.models import CollectionTaskStats

logger = structlog.get_logger(__name__)

# 画像服务内网地址
_PROFILE_APIS: dict[str, str] = {
    "tech":    "http://profile_tech:8001/api/v1/profile/tech/import",
    "project": "http://profile_project:8002/api/v1/profile/project/import",
    "org":     "http://profile_org:8003/api/v1/profile/org/import",
    "person":  "http://profile_person:8004/api/v1/profile/person/import",
}


async def trigger_collection(
    source: DataSourceConfigORM,
    session: AsyncSession,
) -> CollectionTaskORM:
    """创建采集任务记录，后台异步执行采集。"""
    task = CollectionTaskORM(
        source_id=source.id,
        source_name=source.name,
        profile_type=source.profile_type,
        status="pending",
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)

    # 更新数据源最近运行状态
    source.last_run_at = datetime.now(timezone.utc)
    source.last_run_status = "running"

    # 后台运行，不阻塞请求
    asyncio.create_task(_run_collection(task.id, source.config_json, source.source_type, source.profile_type))

    return task


async def _run_collection(
    task_id: int,
    config: dict[str, Any],
    source_type: str,
    profile_type: str,
) -> None:
    """实际采集逻辑，在独立任务中运行。"""
    from metaprofile.shared.db.postgres import get_session

    logs: list[str] = []

    def log(msg: str) -> None:
        logs.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")
        logger.info("collector", task_id=task_id, msg=msg)

    async with get_session() as session:
        task = await session.get(CollectionTaskORM, task_id)
        if not task:
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await session.flush()

        records: list[dict[str, Any]] = []
        error_msg: str | None = None

        try:
            log(f"开始采集，类型={source_type}")

            if source_type == "rest_api":
                records = await _fetch_rest_api(config, log)
            elif source_type == "rss":
                records = await _fetch_rss(config, log)
            elif source_type == "nsfc":
                records = await _fetch_nsfc(config, log)
            elif source_type == "patent_cnipa":
                records = await _fetch_patent_cnipa(config, log)
            elif source_type == "sql_warehouse":
                # ODS→四类画像抽取管线（T13）。collector 自管 profile 写入事务，
                # _run_collection 这层仅跟踪 task 状态；records_imported 由
                # collector 返回的 imported 同步回 task。
                from metaprofile.ingest_ods.collectors.sql_warehouse import (
                    run_sql_warehouse_collection,
                )
                source = await session.get(DataSourceConfigORM, task.source_id)
                imported = await run_sql_warehouse_collection(task=task, source=source)
                task.records_imported = imported
                task.records_fetched = imported
                records = []  # 跳过下方 _import_to_profile（已在 collector 内完成）
                log(f"SQL 仓库采集完成，导入 {imported} 条")
            else:
                raise ValueError(f"不支持的数据源类型: {source_type}")

            if source_type != "sql_warehouse":
                log(f"采集完成，获取 {len(records)} 条原始记录")
                task.records_fetched = len(records)

                if records:
                    imported = await _import_to_profile(records, profile_type, log)
                    task.records_imported = imported

            task.status = "completed"

        except Exception as exc:
            error_msg = str(exc)
            log(f"采集失败: {error_msg}")
            task.status = "failed"
            task.error_msg = error_msg[:500]
        finally:
            task.completed_at = datetime.now(timezone.utc)
            task.log_text = "\n".join(logs[-200:])  # 保留最后200行
            await session.flush()


async def _fetch_rest_api(config: dict[str, Any], log: Any) -> list[dict[str, Any]]:
    """REST API 采集。"""
    url: str = config["url"]
    method: str = config.get("method", "GET").upper()
    headers: dict = config.get("headers", {})
    auth_type: str = config.get("auth_type", "none")
    auth_token: str | None = config.get("auth_token")
    query_params: dict = config.get("query_params", {})
    body_json: dict | None = config.get("body_json")
    items_path: str = config.get("response_items_path", "")
    field_mapping: dict[str, str] = config.get("field_mapping", {})
    pagination_enabled: bool = config.get("pagination_enabled", False)
    page_param: str = config.get("page_param", "page")
    size_param: str = config.get("size_param", "page_size")
    page_size: int = config.get("page_size", 50)
    max_pages: int = config.get("max_pages", 10)

    # 认证头
    if auth_type == "bearer" and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    elif auth_type == "api_key" and auth_token:
        header_name = config.get("auth_header_name", "X-API-Key")
        headers[header_name] = auth_token

    all_items: list[dict] = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pages = range(1, max_pages + 1) if pagination_enabled else range(1, 2)

        for page_num in pages:
            params = dict(query_params)
            if pagination_enabled:
                params[page_param] = page_num
                params[size_param] = page_size

            if method == "GET":
                resp = await client.get(url, headers=headers, params=params)
            else:
                resp = await client.post(url, headers=headers, params=params, json=body_json or params)

            resp.raise_for_status()
            data = resp.json()

            items = _extract_path(data, items_path) if items_path else data
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                break

            log(f"  第{page_num}页获取 {len(items)} 条")
            all_items.extend(items)

            if not pagination_enabled or len(items) < page_size:
                break

    # 字段映射
    if field_mapping:
        mapped = []
        for item in all_items:
            mapped.append({target: _get_nested(item, src) for target, src in field_mapping.items() if _get_nested(item, src) is not None})
        return mapped

    return all_items


async def _fetch_rss(config: dict[str, Any], log: Any) -> list[dict[str, Any]]:
    """RSS/Atom Feed 采集。需要 feedparser。"""
    try:
        import feedparser
    except ImportError:
        raise ImportError("RSS采集需要 feedparser，请执行: pip install feedparser")

    feed_url: str = config["feed_url"]
    field_mapping: dict[str, str] = config.get("field_mapping", {})
    keyword_filter: list[str] = config.get("keyword_filter", [])
    max_items: int = config.get("max_items", 100)

    import asyncio
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

    entries = feed.entries[:max_items]
    log(f"  Feed 共 {len(feed.entries)} 条，取前 {len(entries)} 条")

    results = []
    for entry in entries:
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        if keyword_filter and not any(kw.lower() in text.lower() for kw in keyword_filter):
            continue

        item: dict[str, Any] = {}
        if field_mapping:
            for target, src in field_mapping.items():
                val = entry.get(src)
                if val:
                    item[target] = val
        else:
            item = {
                "tech_name_cn": entry.get("title", ""),
                "tech_name_en": entry.get("title", ""),
                "tech_summary": entry.get("summary", ""),
                "tech_domain": ["待分类"],
                "current_status": "待补充",
                "trend": "待补充",
            }
        results.append(item)

    return results


async def _fetch_nsfc(config: dict[str, Any], log: Any) -> list[dict[str, Any]]:
    """NSFC（国家自然科学基金）公开数据采集（需要合法授权）。"""
    log("NSFC 采集：调用 rest_api 适配器")
    nsfc_config = {
        "url": config.get("url", "https://www.nsfc.gov.cn/publish/portal0/projectsearch/"),
        "method": "POST",
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "query_params": config.get("query_params", {}),
        "field_mapping": config.get("field_mapping", {
            "name_cn": "projectName",
            "tech_domain": "subject",
            "start_date": "approvalYear",
            "main_orgs": "hostUnit",
        }),
        "pagination_enabled": True,
        "page_size": 20,
        "max_pages": config.get("max_pages", 5),
    }
    return await _fetch_rest_api(nsfc_config, log)


async def _fetch_patent_cnipa(config: dict[str, Any], log: Any) -> list[dict[str, Any]]:
    """CNIPA专利数据采集（需要合法授权及API Key）。"""
    log("CNIPA 专利采集")
    cnipa_config = {
        "url": config.get("url", "https://pss-system.cponline.cnipa.gov.cn/seniorSearch/list"),
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.get('api_key', '')}",
        },
        "body_json": {
            "searchKey": config.get("keywords", ""),
            "pageNum": 1,
            "pageSize": 20,
        },
        "response_items_path": "data.records",
        "field_mapping": config.get("field_mapping", {
            "tech_name_cn": "title",
            "tech_name_en": "titleEn",
            "tech_summary": "abstractCn",
            "tech_domain": "ipc",
        }),
        "pagination_enabled": True,
        "page_size": 20,
        "max_pages": config.get("max_pages", 5),
    }
    return await _fetch_rest_api(cnipa_config, log)


async def _import_to_profile(
    records: list[dict[str, Any]],
    profile_type: str,
    log: Any,
) -> int:
    """调画像服务 /import 接口，返回成功导入数量。"""
    api_url = _PROFILE_APIS.get(profile_type)
    if not api_url:
        raise ValueError(f"未知 profile_type: {profile_type}")

    # 过滤空记录
    valid = [r for r in records if r]
    if not valid:
        log("无有效记录可导入")
        return 0

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                api_url,
                json={"profiles": valid, "overwrite": False},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                count = data.get("accepted_count", len(valid))
                log(f"导入成功: {count} 条")
                return count
            else:
                log(f"导入失败 HTTP {resp.status_code}: {resp.text[:200]}")
                return 0
    except Exception as exc:
        log(f"导入异常: {exc}")
        return 0


def _extract_path(data: Any, path: str) -> Any:
    """按点号路径提取嵌套JSON值，如 'data.items'。"""
    parts = path.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
        if cur is None:
            return None
    return cur


def _get_nested(obj: dict, key: str) -> Any:
    """支持点号路径的值获取，如 'user.name'。"""
    if "." in key:
        parts = key.split(".", 1)
        sub = obj.get(parts[0])
        if isinstance(sub, dict):
            return _get_nested(sub, parts[1])
        return None
    return obj.get(key)


async def get_task_stats(db: AsyncSession, task_id: int) -> CollectionTaskStats:
    """聚合单个采集任务的运行统计：ingest_raw 总数/失败数 + ingest_errors 数。

    raw_success = raw_total - raw_failed（status='failed' 之外视为成功）。
    """
    raw_total = (
        await db.execute(
            select(func.count()).select_from(IngestRawORM).where(
                IngestRawORM.batch_id == task_id
            )
        )
    ).scalar_one()

    raw_failed = (
        await db.execute(
            select(func.count()).select_from(IngestRawORM).where(
                IngestRawORM.batch_id == task_id,
                IngestRawORM.status == "failed",
            )
        )
    ).scalar_one()

    errors = (
        await db.execute(
            select(func.count()).select_from(IngestErrorORM).where(
                IngestErrorORM.batch_id == task_id
            )
        )
    ).scalar_one()

    return CollectionTaskStats(
        task_id=task_id,
        raw_total=raw_total,
        raw_success=max(raw_total - raw_failed, 0),
        raw_failed=raw_failed,
        errors=errors,
    )

