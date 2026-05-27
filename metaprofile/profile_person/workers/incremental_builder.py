"""人员画像增量构建任务（每日运行）。"""
from __future__ import annotations

import structlog

from metaprofile.profile_person.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="metaprofile.profile_person.workers.incremental_builder.run")
def run() -> dict:
    """从昨日清洗后的中间表抓取新数据，跑 NER + 抽取 + 入库。

    流程：
    1. 查询 cleaned_data WHERE source_date = yesterday AND processed = false
    2. 按批次（默认 100 条/批）调用 foundation.ner + foundation.extractors.person_extractor
    3. 走消歧（auto_merge / llm_judge）
    4. 写入 PostgreSQL + ES + Neo4j（unified_repo）
    5. 标记 processed = true
    """
    logger.info("tech_incremental_build_started")
    # TODO: 实现详见 CLAUDE_CODE_PLAN 阶段 3
    return {"status": "ok", "processed": 0}
