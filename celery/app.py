import time

from celery import group
from fastapi import FastAPI
from pydantic import BaseModel, Field

from tasks import long_task

app = FastAPI()


class StartRequest(BaseModel):
    count: int = Field(default=200, ge=1, le=1000)


@app.post("/start")
async def start_task(body: StartRequest):
    start_time = time.time()

    results = group(
        long_task.s(task_id) for task_id in range(1, body.count + 1)
    ).apply_async().get(timeout=3600)

    total_time = round(time.time() - start_time, 2)
    task_count = len(results)
    message = f"All {task_count} tasks completed in {total_time:.2f} seconds"

    print(message, flush=True)
    return {
        "task_count": task_count,
        "total_time_seconds": total_time,
        "avg_time_per_task_seconds": round(total_time / task_count, 2),
        "message": message,
    }
