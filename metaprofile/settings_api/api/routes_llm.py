from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.session import get_db
from metaprofile.settings_api.domain.orm_models import LLMProviderConfigORM
from metaprofile.settings_api.schemas.models import (
    LLMProviderConfigCreate,
    LLMProviderConfigOut,
    LLMProviderConfigUpdate,
    LLMTestResponse,
)
from metaprofile.settings_api.services.llm_sync_service import sync_to_litellm, test_llm_connection

router = APIRouter(prefix="/api/v1/settings/llm", tags=["LLM配置"])


@router.get("", response_model=list[LLMProviderConfigOut])
async def list_llm_configs(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(LLMProviderConfigORM).order_by(LLMProviderConfigORM.id))).scalars().all()
    return rows


@router.post("", response_model=LLMProviderConfigOut, status_code=201)
async def create_llm_config(body: LLMProviderConfigCreate, db: AsyncSession = Depends(get_db)):
    # 如果设为default，清除同role其他default
    if body.is_default:
        await _clear_default(db, body.model_role, None)

    cfg = LLMProviderConfigORM(**body.model_dump())
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)

    synced = await sync_to_litellm(cfg)
    cfg.litellm_synced = synced
    await db.flush()

    return cfg


@router.put("/{cfg_id}", response_model=LLMProviderConfigOut)
async def update_llm_config(cfg_id: int, body: LLMProviderConfigUpdate, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(LLMProviderConfigORM, cfg_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")

    updates = body.model_dump(exclude_none=True)
    if updates.get("is_default"):
        await _clear_default(db, cfg.model_role, cfg_id)

    for k, v in updates.items():
        setattr(cfg, k, v)

    cfg.litellm_synced = False  # 标记需重新同步
    synced = await sync_to_litellm(cfg)
    cfg.litellm_synced = synced
    await db.flush()
    await db.refresh(cfg)  # 加载 updated_at 等，避免响应序列化触发懒加载(MissingGreenlet)

    return cfg


@router.delete("/{cfg_id}", status_code=204)
async def delete_llm_config(cfg_id: int, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(LLMProviderConfigORM, cfg_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")
    await db.delete(cfg)


@router.post("/{cfg_id}/test", response_model=LLMTestResponse)
async def test_llm_config(cfg_id: int, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(LLMProviderConfigORM, cfg_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")
    success, message, latency = await test_llm_connection(cfg)
    return LLMTestResponse(success=success, message=message, latency_ms=latency)


@router.post("/{cfg_id}/sync", response_model=LLMProviderConfigOut)
async def sync_llm_config(cfg_id: int, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(LLMProviderConfigORM, cfg_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")
    synced = await sync_to_litellm(cfg)
    cfg.litellm_synced = synced
    await db.flush()
    return cfg


async def _clear_default(db: AsyncSession, role: str, exclude_id: int | None) -> None:
    rows = (await db.execute(
        select(LLMProviderConfigORM).where(
            LLMProviderConfigORM.model_role == role,
            LLMProviderConfigORM.is_default == True,
        )
    )).scalars().all()
    for r in rows:
        if r.id != exclude_id:
            r.is_default = False
