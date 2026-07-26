import time

from celery_app import celery


@celery.task
def long_task(task_id: int):
    """Heavy task: extract -> OpenAI -> store."""
    label = f"process-{task_id}"

    print(f"[process] Extracting text from {label}")
    time.sleep(0.15)

    print(f"[process] Calling OpenAI API for {label}")
    time.sleep(4.5)
    summary = f"Summary of {label}"

    print(f"[process] Storing result for {label} in DB")
    time.sleep(0.1)

    return {
        "task_type": "process",
        "task_id": task_id,
        "summary": summary,
    }


@celery.task
def notify_task(task_id: int):
    """Light task: send notification after processing."""
    label = f"notify-{task_id}"

    print(f"[notify] Sending notification for {label}")
    time.sleep(0.2)

    return {
        "task_type": "notify",
        "task_id": task_id,
        "status": "sent",
    }
