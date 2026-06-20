"""共享 Celery 应用。

供 enrich 等需要异步队列的消费任务使用（broker=RabbitMQ, backend=Redis）。
取代 4 画像各自重复的 profile_*/workers/celery_app.py。
"""
from __future__ import annotations

from celery import Celery

from metaprofile.shared.config.settings import settings

celery_app = Celery(
    "metaprofile",
    broker=settings.rabbitmq.url,
    backend=str(settings.redis.dsn),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 任务自动发现（worker 启动时 import 注册）
    include=[
        "metaprofile.shared.worker.enrich_tasks",
        "metaprofile.shared.worker.scan_tasks",
    ],
)
