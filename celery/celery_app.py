import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:8231/0")

celery = Celery(
    "demo",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)