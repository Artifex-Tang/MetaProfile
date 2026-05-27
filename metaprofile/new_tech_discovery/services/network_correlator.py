"""信号关联网络构建：将弱信号与关联实体（技术/机构/人物）连接成图。

从 profile 层拉取共现关系，构建 SignalNetworkEdge 并持久化。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import SignalNetworkEdgeORM, WeakSignalORM
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


class NetworkCorrelator:
    """弱信号关联网络构建器。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._tech_base = settings.profile_api.tech_base_url
        self._org_base = settings.profile_api.org_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def build_network(
        self,
        *,
        signal: WeakSignalORM,
        period_from: date,
        period_to: date,
    ) -> list[SignalNetworkEdgeORM]:
        """为单个弱信号构建关联网络边，写入 DB 后返回。"""
        edges: list[SignalNetworkEdgeORM] = []

        tech_peers = await self._fetch_related_techs(signal.domain, period_from, period_to)
        for peer_id in tech_peers:
            if peer_id in (signal.related_tech_ids or []):
                continue
            edge = SignalNetworkEdgeORM(
                signal_id=signal.signal_id,
                source_id=signal.signal_id,
                source_type="signal",
                target_id=peer_id,
                target_type="tech",
                edge_type="co_domain",
                weight=0.5,
            )
            self._db.add(edge)
            edges.append(edge)

        for tid in (signal.related_tech_ids or []):
            edge = SignalNetworkEdgeORM(
                signal_id=signal.signal_id,
                source_id=signal.signal_id,
                source_type="signal",
                target_id=tid,
                target_type="tech",
                edge_type="co_occurrence",
                weight=1.0,
            )
            self._db.add(edge)
            edges.append(edge)

        for oid in (signal.related_org_ids or []):
            edge = SignalNetworkEdgeORM(
                signal_id=signal.signal_id,
                source_id=signal.signal_id,
                source_type="signal",
                target_id=oid,
                target_type="org",
                edge_type="funding",
                weight=0.8,
            )
            self._db.add(edge)
            edges.append(edge)

        for pid in (signal.related_person_ids or []):
            edge = SignalNetworkEdgeORM(
                signal_id=signal.signal_id,
                source_id=signal.signal_id,
                source_type="signal",
                target_id=pid,
                target_type="person",
                edge_type="authorship",
                weight=0.6,
            )
            self._db.add(edge)
            edges.append(edge)

        await self._db.flush()
        return edges

    async def _fetch_related_techs(
        self, domain: str | None, period_from: date, period_to: date
    ) -> list[str]:
        """从 profile_tech 搜索同域技术 ID。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 10}
                if domain:
                    body["tech_domain"] = [domain]
                resp = await client.post(
                    f"{self._tech_base}{settings.api_prefix}/profile/tech/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return []
                return [item["tech_id"] for item in resp.json().get("items", []) if item.get("tech_id")]
        except Exception as exc:
            logger.warning("network_correlator_fetch_failed", error=str(exc))
            return []
