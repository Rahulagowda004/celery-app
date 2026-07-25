import time
from pathlib import Path

from pypdf import PdfReader

from celery_app import celery


@celery.task
def long_task(pdf_path: str):
    path = Path(pdf_path)
    print(f"Extracting text from {path.name}")

    reader = PdfReader(path)
    pages_text = []

    for i, page in enumerate(reader.pages, start=1):
        print(f"Processing page {i}/{len(reader.pages)}")
        pages_text.append(page.extract_text() or "")

    text = "\n".join(pages_text)
    print(f"Finished extracting {len(text)} characters from {path.name}")

    return {
        "filename": path.name,
        "page_count": len(reader.pages),
        "char_count": len(text),
    }


@celery.task
def summarize_batch(results: list[dict], start_time: float):
    total_time = time.perf_counter() - start_time
    message = f"All {len(results)} tasks completed in {total_time:.2f} seconds"
    print(message, flush=True)

    return {
        "task_count": len(results),
        "total_time_seconds": round(total_time, 2),
        "message": message,
        "results": results,
    }
