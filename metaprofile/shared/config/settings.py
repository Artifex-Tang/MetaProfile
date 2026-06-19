"""
全局配置加载（pydantic-settings）。

所有模块都应通过 `from metaprofile.shared.config.settings import settings`
来获取配置，禁止直接读 os.environ。
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")
    dsn: PostgresDsn = "postgresql+asyncpg://postgres:postgres@localhost:5432/metaprofile"  # type: ignore[assignment]
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False


class ESSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ES_")
    hosts: list[str] = Field(default_factory=lambda: ["http://localhost:9200"])
    username: str | None = None
    password: str | None = None
    profile_index_prefix: str = "metaprofile_"
    embedding_dim: int = 1024  # BGE-large-zh 维度


class Neo4jSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEO4J_")
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "metaprofile"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    dsn: RedisDsn = "redis://localhost:6379/0"


class RabbitMQSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")
    url: str = "amqp://guest:guest@localhost:5672//"


class LLMSettings(BaseSettings):
    """LLM 网关与模型配置。所有 LLM 调用走 LiteLLM Proxy。"""
    model_config = SettingsConfigDict(env_prefix="LLM_")
    proxy_base_url: str = "http://localhost:4000"
    proxy_api_key: str = ""
    extraction_model: str = "qwen2.5-72b-instruct"   # Schema-Guided IE
    relation_model: str = "qwen2.5-72b-instruct"     # 关系分类
    judge_model: str = "qwen2.5-72b-instruct"        # 消歧判定
    agent_model: str = "qwen2.5-72b-instruct"        # 前沿性 Agent 验证
    generation_model: str = "deepseek-chat"          # 选题生成等长文本
    embedding_model: str = "bge-large-zh-v1.5"
    timeout_seconds: int = 60
    max_retries: int = 3
    confidence_threshold_extract: float = 0.7
    confidence_threshold_disambig: float = 0.7


class CollectorSettings(BaseSettings):
    """各数据源采集器配置。API Key 等敏感信息通过环境变量注入。"""
    model_config = SettingsConfigDict(env_prefix="COLLECTOR_")

    # 通用
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_rps: float = 2.0  # 每秒最多请求数（礼貌爬取）

    # CNIPA 国知局专利
    cnipa_base_url: str = "https://pss-system.cponline.cnipa.gov.cn"
    cnipa_api_key: str = ""

    # WIPO PatentScope
    wipo_base_url: str = "https://patentscope.wipo.int/search/en/search.jsf"
    wipo_api_key: str = ""

    # CNKI
    cnki_base_url: str = "https://api.cnki.net"
    cnki_api_key: str = ""

    # Web of Science
    wos_base_url: str = "https://api.clarivate.com/apis/wos-starter/v1"
    wos_api_key: str = ""

    # NSFC 国家自然科学基金
    nsfc_base_url: str = "https://www.nsfc.gov.cn"
    nsfc_api_key: str = ""

    # 天眼查
    tianyancha_base_url: str = "https://open.tianyancha.com/cloud-other-information"
    tianyancha_api_key: str = ""

    # 政府门户（通用）
    policy_gov_base_url: str = "https://www.gov.cn"

    # 中国政府采购网
    ccgp_base_url: str = "https://www.ccgp.gov.cn"


class ProfileApiSettings(BaseSettings):
    """四画像层 REST API 基地址（分析层通过此调用画像层，不直读 DB）。"""
    model_config = SettingsConfigDict(env_prefix="PROFILE_API_")
    tech_base_url: str = "http://localhost:8001"
    project_base_url: str = "http://localhost:8002"
    org_base_url: str = "http://localhost:8003"
    person_base_url: str = "http://localhost:8004"
    timeout_seconds: int = 30


class StorageThresholds(BaseSettings):
    """阈值集中管理，禁止散落在业务代码中。"""
    model_config = SettingsConfigDict(env_prefix="THRESHOLD_")
    ner_confidence_min: float = 0.7
    disambig_auto_merge: float = 0.95
    disambig_llm_judge_min: float = 0.70
    completeness_enrich_trigger: float = 0.60
    enrichment_auto_accept: float = 0.80
    enrichment_review_min: float = 0.60
    # ── 数据质量评分（规则型，ISO 25012 对齐；详见 quality_rules.py）──
    # 来源可信度基线（按数据进入通道）
    source_trust_ods: float = 0.90        # ODS Doris 官方库（sql_warehouse 抽取）
    source_trust_llm: float = 0.70        # LLM 补全（enrich）
    source_trust_import: float = 0.60     # 批量导入 JSON / 手工
    source_trust_ugc: float = 0.40        # UGC / 网页抓取
    source_trust_unknown: float = 0.50    # 缺来源信息兜底
    authority_bonus_each: float = 0.05    # 每个权威信号加分（DOI/引用/官方编号）
    authority_bonus_cap: float = 0.15     # 权威加分上限
    consistency_factor_ok: float = 1.0    # 跨字段一致
    consistency_factor_bad: float = 0.85  # 任一一致性检查失败
    timeliness_halflife_days: int = 180   # 时效指数衰减半衰期
    dq_weight_completeness: float = 0.4   # 复合 DQI 权重（Σ=1.0，可调）
    dq_weight_veracity: float = 0.3
    dq_weight_timeliness: float = 0.3


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    service_name: str = "metaprofile"
    secret_key: str = "dev-insecure-key"

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    es: ESSettings = Field(default_factory=ESSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    thresholds: StorageThresholds = Field(default_factory=StorageThresholds)
    collectors: CollectorSettings = Field(default_factory=CollectorSettings)
    profile_api: ProfileApiSettings = Field(default_factory=ProfileApiSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
