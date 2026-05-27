"""pytest 配置：在模块导入前注入测试环境变量。"""
from __future__ import annotations

import os

# 在任何 metaprofile 模块被导入前设好环境变量（settings 模块级实例化需要）
os.environ.setdefault(
    "POSTGRES_DSN",
    "postgresql+asyncpg://test:test@localhost:5432/test_metaprofile",
)
os.environ.setdefault("REDIS_DSN", "redis://localhost:6379/15")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("LLM_PROXY_API_KEY", "test-key")
