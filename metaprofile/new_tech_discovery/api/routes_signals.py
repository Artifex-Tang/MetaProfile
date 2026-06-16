"""弱信号查询 API。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import SignalNetworkEdgeORM, WeakSignalORM
from metaprofile.new_tech_discovery.schemas.models import (
    SignalNetwork,
    SignalNetworkEdge,
    SignalNetworkNode,
    WeakSignalItem,
    WeakSignalList,
)
from metaprofile.shared.db.session import get_db

router = APIRouter()


@router.get("/new-tech/signals", response_model=WeakSignalList)
async def list_signals(
    domain: str | None = Query(default=None),
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0),
    period_from: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> WeakSignalList:
    """查询识别出的弱信号清单。"""
    from sqlalchemy import func
    q = select(WeakSignalORM).where(
        WeakSignalORM.strength >= min_strength
    ).order_by(desc(WeakSignalORM.strength))
    if domain:
        q = q.where(WeakSignalORM.domain == domain)
    if period_from:
        q = q.where(WeakSignalORM.period_from >= period_from)

    total_base = select(WeakSignalORM).where(WeakSignalORM.strength >= min_strength)
    if domain:
        total_base = total_base.where(WeakSignalORM.domain == domain)
    if period_from:
        total_base = total_base.where(WeakSignalORM.period_from >= period_from)
    total = (await db.execute(select(func.count()).select_from(total_base.subquery()))).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return WeakSignalList(
        items=[WeakSignalItem.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/new-tech/signals/{signal_id}/network", response_model=SignalNetwork)
async def get_signal_network(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
) -> SignalNetwork:
    """查询某弱信号的关联网络（节点：相关技术/机构/人物；边：共现/引用/资助等）。"""
    edges_rows = (await db.execute(
        select(SignalNetworkEdgeORM).where(SignalNetworkEdgeORM.signal_id == signal_id)
    )).scalars().all()

    nodes: list[SignalNetworkNode] = []
    seen: set[str] = set()
    edges: list[SignalNetworkEdge] = []
    for e in edges_rows:
        for eid, etype in [(e.source_id, e.source_type), (e.target_id, e.target_type)]:
            if eid not in seen:
                nodes.append(SignalNetworkNode(entity_id=eid, entity_type=etype))
                seen.add(eid)
        edges.append(SignalNetworkEdge(
            source_id=e.source_id,
            target_id=e.target_id,
            edge_type=e.edge_type,
            weight=e.weight,
        ))
    # 解析实体名称（按类型批量查询各画像表），避免前端只显示 ID
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    from metaprofile.profile_org.domain.orm_models import OrgProfileORM
    from metaprofile.profile_person.domain.orm_models import PersonProfileORM
    from metaprofile.profile_project.domain.orm_models import ProjectProfileORM

    by_type: dict[str, set[str]] = {}
    for n in nodes:
        by_type.setdefault(n.entity_type.lower(), set()).add(n.entity_id)

    name_map: dict[str, str] = {}
    table_map = {
        "tech": (TechProfileORM, "tech_name_cn"),
        "org": (OrgProfileORM, "name_cn"),
        "person": (PersonProfileORM, "name_cn"),
        "project": (ProjectProfileORM, "name_cn"),
    }
    for etype, ids in by_type.items():
        if etype not in table_map or not ids:
            continue
        orm_cls, name_col = table_map[etype]
        rows = (await db.execute(
            select(getattr(orm_cls, "id") if False else orm_cls).where(
                getattr(orm_cls, f"{etype}_id").in_(ids)
            )
        )).scalars().all()
        for r in rows:
            rid = getattr(r, f"{etype}_id")
            val = getattr(r, name_col)
            name_map[rid] = (val[0] if isinstance(val, list) and val else val) or rid

    for n in nodes:
        n.name = name_map.get(n.entity_id)

    return SignalNetwork(signal_id=signal_id, nodes=nodes, edges=edges)
