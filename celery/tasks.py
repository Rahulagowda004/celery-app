import time

from celery_app import celery


@celery.task
def long_task(task_id: int):
    label = f"task-{task_id}"

    print(f"Extracting text from {label}")
    time.sleep(0.15)

    print(f"Calling OpenAI API for {label}")
    time.sleep(4.5)
    summary = f"Summary of {label}"

    print(f"Storing result for {label} in DB")
    time.sleep(0.1)

    return {
        "task_id": task_id,
        "summary": summary,
    }
