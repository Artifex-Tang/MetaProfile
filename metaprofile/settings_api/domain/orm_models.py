from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class LLMProviderConfigORM(Base, TimestampMixin):
    """LLM 提供商配置。存储各大模型厂商的接入参数。"""

    __tablename__ = "llm_provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="显示名称")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, comment="厂商: openai/dashscope/deepseek/anthropic/ollama/custom")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模型标识")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="API Key（明文，生产环境建议加密）")
    api_base: Mapped[str | None] = mapped_column(Text, nullable=True, comment="自定义 Base URL")
    model_role: Mapped[str] = mapped_column(String(32), nullable=False, default="general", comment="extraction/generation/embedding/general")
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="该角色的默认模型")
    litellm_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已同步到 LiteLLM Proxy")


class DataSourceConfigORM(Base, TimestampMixin):
    """数据源配置。定义外部数据的接入方式。"""

    __tablename__ = "data_source_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据源显示名称")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="rest_api/rss/web_page/nsfc/patent_cnipa")
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="tech/project/org/person")
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="数据源详细配置（URL、认证、字段映射等）")
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="定时采集 cron 表达式，如 0 2 * * *")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="success/failed/running")


class CollectionTaskORM(Base, TimestampMixin):
    """采集任务记录。每次触发采集生成一条记录。"""

    __tablename__ = "collection_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="关联数据源ID")
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="pending/running/completed/failed")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class EnrichmentTaskORM(Base, TimestampMixin):
    """LLM 补全（enrich）任务记录。每次触发补全生成一条，供任务列表查看历史。

    celery AsyncResult 过期即丢，故落库：trigger 写 queued 行，worker 写终态。
    """

    __tablename__ = "enrichment_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="tech/project/org/person")
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="celery task_id")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued",
        comment="queued/running/done/skipped/no_fill/failed/error",
    )
    filled_fields: Mapped[list] = mapped_column(JSONB, default=list, comment="本次补全填充的字段")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
