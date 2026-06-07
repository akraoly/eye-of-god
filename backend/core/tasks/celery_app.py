"""
Celery application — L'Œil de Dieu
Broker/backend : Redis localhost:6379
"""
from celery import Celery

celery_app = Celery(
    "eye_of_god",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=[
        "core.tasks.pentest_tasks",
        "core.tasks.osint_tasks",
        "core.tasks.exploit_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=600,   # 10 min soft limit
    task_time_limit=1800,       # 30 min hard limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
