import time
import uuid
from pathlib import Path

from celery import chord
from fastapi import FastAPI, File, HTTPException, UploadFile

from tasks import long_task, summarize_batch

app = FastAPI()

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


async def _save_pdf(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    file_path.write_bytes(await file.read())
    return file_path


@app.post("/start")
async def start_task(files: list[UploadFile] = File(...)):
    if not files:
       raise HTTPException(status_code=400, detail="At least one PDF file is required")

    file_paths = [await _save_pdf(file) for file in files]
    start_time = time.perf_counter()

    result = chord(
        (long_task.s(str(path)) for path in file_paths),
        summarize_batch.s(start_time),
    ).apply_async().get(timeout=600)

    print(result["message"], flush=True)
    return result
