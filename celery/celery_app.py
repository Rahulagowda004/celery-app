from celery import Celery

celery = Celery(
    "demo",
    broker="redis://localhost:8231/0",
    backend="redis://localhost:8231/0",
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)