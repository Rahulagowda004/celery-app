import time

from celery import group
from fastapi import FastAPI
from pydantic import BaseModel, Field

from tasks import long_task, notify_task

app = FastAPI()


class CountRequest(BaseModel):
    count: int = Field(default=200, ge=1, le=1000)


def _build_response(task_type: str, results: list[dict], start_time: float) -> dict:
    total_time = round(time.time() - start_time, 2)
    task_count = len(results)
    message = f"All {task_count} {task_type} tasks completed in {total_time:.2f} seconds"
    print(message, flush=True)

    return {
        "task_type": task_type,
        "task_count": task_count,
        "total_time_seconds": total_time,
        "avg_time_per_task_seconds": round(total_time / task_count, 2),
        "message": message,
    }


@app.post("/start-process")
async def start_process(body: CountRequest):
    start_time = time.time()

    results = group(
        long_task.s(task_id) for task_id in range(1, body.count + 1)
    ).apply_async().get(timeout=3600)

    return _build_response("process", results, start_time)


@app.post("/start-notify")
async def start_notify(body: CountRequest):
    start_time = time.time()

    results = group(
        notify_task.s(task_id) for task_id in range(1, body.count + 1)
    ).apply_async().get(timeout=3600)

    return _build_response("notify", results, start_time)
