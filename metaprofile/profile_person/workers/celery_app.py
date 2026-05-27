"""人员画像 Celery 应用。"""
from __future__ import annotations

from celery import Celery

from metaprofile.shared.config.settings import settings

celery_app = Celery(
    "profile_person",
    broker=settings.rabbitmq.url,
    backend=str(settings.redis.dsn),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    # 每日 02:00 增量构建
    "tech-incremental-build": {
        "task": "metaprofile.profile_person.workers.incremental_builder.run",
        "schedule": 86400.0,  # 实际项目用 crontab(hour=2)
    },
    # 每周日 03:00 RAG 补全
    "tech-enrichment": {
        "task": "metaprofile.profile_person.workers.enrichment_worker.scan_and_enrich",
        "schedule": 604800.0,  # 实际项目用 crontab(day_of_week=0, hour=3)
    },
    # 每日 01:00 统计
    "tech-stats": {
        "task": "metaprofile.profile_person.workers.stats_worker.compute_daily",
        "schedule": 86400.0,
    },
    # 每月 1 号 04:00 全量重建
    "tech-full-rebuild": {
        "task": "metaprofile.profile_person.workers.full_rebuilder.run",
        "schedule": 2592000.0,
    },
}
