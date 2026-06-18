from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderConfigCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., description="openai/dashscope/deepseek/anthropic/ollama/custom")
    model_name: str = Field(..., min_length=1)
    api_key: str | None = None
    api_base: str | None = None
    model_role: str = Field(default="general", description="extraction/generation/embedding/general")
    max_tokens: int = Field(default=4096, ge=256, le=128000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    is_enabled: bool = True
    is_default: bool = False


class LLMProviderConfigUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    model_role: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None


class LLMProviderConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    model_name: str
    api_key: str | None  # 前端显示时建议脱敏
    api_base: str | None
    model_role: str
    max_tokens: int
    temperature: float
    is_enabled: bool
    is_default: bool
    litellm_synced: bool
    created_at: datetime
    updated_at: datetime

    def model_post_init(self, __context: Any) -> None:
        # 脱敏：只保留前8位
        if self.api_key and len(self.api_key) > 8:
            object.__setattr__(self, 'api_key', self.api_key[:8] + '***')


# ── 数据源配置 ──────────────────────────────────────────────────────────────

class RestApiSourceConfig(BaseModel):
    """REST API 数据源配置。"""
    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    auth_type: str = Field(default="none", description="none/bearer/api_key/basic")
    auth_token: str | None = None
    auth_header_name: str = "Authorization"
    query_params: dict[str, Any] = Field(default_factory=dict)
    body_json: dict[str, Any] | None = None
    response_items_path: str = Field(default="", description="JSON路径提取列表，如 data.items，空则直接用响应体")
    field_mapping: dict[str, str] = Field(default_factory=dict, description="目标字段 → 源字段名")
    pagination_enabled: bool = False
    pagination_type: str = Field(default="page", description="page/offset/cursor/none")
    page_param: str = "page"
    size_param: str = "page_size"
    page_size: int = 50
    max_pages: int = 10


class RssSourceConfig(BaseModel):
    """RSS/Atom Feed 数据源配置。"""
    feed_url: str
    field_mapping: dict[str, str] = Field(default_factory=dict)
    keyword_filter: list[str] = Field(default_factory=list, description="含有这些关键词的条目才录入")
    max_items: int = 100


class DataSourceConfigCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=128)
    source_type: str = Field(..., description="rest_api/rss/web_page/nsfc/patent_cnipa")
    profile_type: str = Field(..., description="tech/project/org/person")
    config_json: dict[str, Any] = Field(default_factory=dict)
    schedule_cron: str | None = None
    is_enabled: bool = True


class DataSourceConfigUpdate(BaseModel):
    name: str | None = None
    config_json: dict[str, Any] | None = None
    schedule_cron: str | None = None
    is_enabled: bool | None = None


class DataSourceConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    profile_type: str
    config_json: dict[str, Any]
    schedule_cron: str | None
    is_enabled: bool
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime
    updated_at: datetime


# ── 采集任务 ──────────────────────────────────────────────────────────────────

class CollectionTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str
    profile_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    records_fetched: int
    records_imported: int
    error_msg: str | None
    log_text: str | None
    created_at: datetime


class TriggerCollectionResponse(BaseModel):
    task_id: int
    source_id: int
    source_name: str
    status: str = "pending"
    message: str


# ── 数据连接（ODS Doris 等外部 DB，密码加密）─────────────────────────────────

class DbConnectionCreate(BaseModel):
    name: str
    dialect: str = "doris"
    host: str
    port: int
    database: str
    username: str
    password: str  # 明文，服务层加密存 password_enc
    charset: str = "utf8mb4"
    pool_size: int = 8
    read_only: bool = True
    is_enabled: bool = True


class DbConnectionUpdate(BaseModel):
    name: str | None = None
    dialect: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None  # 提供则重新加密
    charset: str | None = None
    pool_size: int | None = None
    read_only: bool | None = None
    is_enabled: bool | None = None


class DbConnectionOut(BaseModel):
    """脱敏输出：不含 password_enc。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    dialect: str
    host: str
    port: int
    database: str
    username: str
    charset: str
    pool_size: int
    read_only: bool
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# ── 采集任务运行统计（ingest_raw / ingest_errors 聚合）────────────────────────

class CollectionTaskStats(BaseModel):
    task_id: int
    raw_total: int = 0
    raw_success: int = 0
    raw_failed: int = 0
    errors: int = 0


class LLMTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
