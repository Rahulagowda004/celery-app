# Celery Learning Notes

Everything covered while building this project — from basics to scaling, Windows quirks, and the PDF batch pipeline.

---

## Table of Contents

1. [What is Celery?](#1-what-is-celery)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [How Each File Works](#4-how-each-file-works)
5. [Running the Stack](#5-running-the-stack)
6. [Redis Setup (Docker)](#6-redis-setup-docker)
7. [Worker Pools on Windows](#7-worker-pools-on-windows)
8. [PDF Text Extraction Task](#8-pdf-text-extraction-task)
9. [Batch API with Timing](#9-batch-api-with-timing)
10. [Uploading PDFs (PowerShell)](#10-uploading-pdfs-powershell)
11. [Scaling Workers](#11-scaling-workers)
12. [Calculating Workers & Concurrency](#12-calculating-workers--concurrency)
13. [Common Errors & Fixes](#13-common-errors--fixes)

---

## 1. What is Celery?

Celery is a **distributed task queue**. It lets you run slow or heavy work **in the background** instead of blocking your web server.

**Without Celery:**
```
Client → API → [waits 10 seconds] → response
```

**With Celery:**
```
Client → API → returns immediately with task_id
                ↓
              Redis queue
                ↓
              Worker → does the actual work
```

---

## 2. Architecture

```
┌─────────────┐     POST /start      ┌─────────────┐
│   FastAPI   │ ──────────────────►  │    Redis    │
│   (app.py)  │     queue task       │   (broker)  │
└─────────────┘                      └──────┬──────┘
                                            │
                                            ▼
                                     ┌─────────────┐
                                     │   Celery    │
                                     │   Worker    │
                                     │  (tasks.py) │
                                     └──────┬──────┘
                                            │
                                            ▼
                                     ┌─────────────┐
                                     │    Redis    │
                                     │  (backend)  │
                                     └─────────────┘
```

| Component | Role |
|---|---|
| **Producer** | FastAPI — receives HTTP requests, queues tasks |
| **Broker** | Redis — holds the task queue (messages waiting to run) |
| **Worker** | Celery process — pulls tasks and executes them |
| **Result backend** | Redis — stores task return values |

### Task lifecycle

1. Client sends `POST /start` with PDF files
2. FastAPI saves files and queues tasks via Celery `chord`
3. Celery serializes task + arguments to JSON and pushes to Redis
4. Worker picks up tasks and runs `long_task` for each PDF
5. When all finish, `summarize_batch` runs and prints total time
6. API returns results + `total_time_seconds`

---

## 3. Project Structure

```
celery-practise/
├── celery/
│   ├── celery_app.py      # Celery app config (broker, backend, serializers)
│   ├── tasks.py           # Celery tasks (long_task, summarize_batch)
│   ├── app.py             # FastAPI API (POST /start)
│   ├── docker-compose.yaml
│   └── uploads/           # Saved PDFs (gitignored)
├── resumes/               # Sample PDFs for testing
└── CELERY_NOTES.md
```

> **Important:** Run all commands from the `celery/` directory — that's where `tasks.py` lives.

---

## 4. How Each File Works

### `celery_app.py` — Celery application

```python
celery = Celery(
    "demo",
    broker="redis://localhost:8231/0",
    backend="redis://localhost:8231/0",
)
```

- `"demo"` — app name (for logging)
- `broker` — where tasks are sent
- `backend` — where results are stored
- JSON serializers — task args and return values must be JSON-serializable

### `tasks.py` — the work

| Task | Purpose |
|---|---|
| `long_task` | Extracts text from a PDF using `pypdf` |
| `summarize_batch` | Runs after all tasks in a batch finish; prints and returns total time |

`@celery.task` turns a normal function into a remote procedure:
- `long_task(path)` — runs immediately (for testing)
- `long_task.delay(path)` — sends to queue, returns `AsyncResult`
- `long_task.apply_async(args=[path])` — same, with more options

### `app.py` — the API

- `POST /start` — accepts **multiple PDFs** (`files` field)
- Saves each PDF to `uploads/`
- Uses Celery **chord** to run all extractions in parallel, then `summarize_batch`
- Blocks until all tasks complete (up to 10 min timeout)
- Prints and returns total execution time

---

## 5. Running the Stack

You need **three things** running:

| Terminal | Directory | Command |
|---|---|---|
| 1 — Redis | `celery/` | `docker compose up -d` |
| 2 — Worker | `celery/` | `python -m celery -A tasks worker --loglevel=info --pool=threads --concurrency=8` |
| 3 — API | `celery/` | `python -m uvicorn app:app --reload` |

Then test at **http://localhost:8000/docs** or use the upload commands below.

---

## 6. Redis Setup (Docker)

`docker-compose.yaml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "8231:6379"   # host:container
```

**Critical:** Redis listens on port **6379 inside the container**. The mapping must be `8231:6379`, not `8231:8231`.

| Wrong | Right |
|---|---|
| `"8231:8231"` | `"8231:6379"` |

Wrong mapping causes: `Cannot connect to redis://localhost:8231/0: Connection closed by server`

Verify Redis is up:

```powershell
docker compose ps
```

---

## 7. Worker Pools on Windows

| Pool | Parallelism on Windows | When to use |
|---|---|---|
| `prefork` (default) | Unreliable | Linux/Docker only |
| `solo` | None (1 task at a time) | Simple debugging |
| **`threads`** | Yes | **Best for Windows** |
| `gevent` / `eventlet` | Possible | Needs extra packages |

### Commands

```powershell
# Windows (recommended)
python -m celery -A tasks worker --loglevel=info --pool=threads --concurrency=8

# Windows (no parallelism)
python -m celery -A tasks worker --loglevel=info --pool=solo

# Linux / Docker (production)
python -m celery -A tasks worker --loglevel=info --autoscale=10,1
```

`--autoscale=MAX,MIN` only works with **prefork** on Linux. Format is max first, then min (e.g. `10,1` = 1–10 processes per worker).

---

## 8. PDF Text Extraction Task

`long_task` uses `pypdf` to read each page and return:

```json
{
  "filename": "resume.pdf",
  "page_count": 2,
  "char_count": 4436
}
```

**Note:** `pypdf` works on text-based PDFs. Scanned/image PDFs need OCR (e.g. Tesseract).

---

## 9. Batch API with Timing

### Why chord?

- **`group`** — runs tasks in parallel but doesn't give you one "all done" callback
- **`chord`** — runs a group of tasks, then a callback when **all** finish

Flow:

```
POST /start (multiple PDFs)
    │
    ├─► long_task(pdf1)  ─┐
    ├─► long_task(pdf2)  ─┼─► summarize_batch() → prints total time
    └─► long_task(pdf3)  ─┘
```

### Example response

```json
{
  "task_count": 7,
  "total_time_seconds": 0.23,
  "message": "All 7 tasks completed in 0.23 seconds",
  "results": [ ... ]
}
```

Total time appears in:
- **Worker terminal** (from `summarize_batch`)
- **API terminal** (from `app.py`)
- **JSON response** (`total_time_seconds`)

### Important

- Use **one API call** with all files — not a loop of separate requests
- Form field name is **`files`** (plural), not `file`

---

## 10. Uploading PDFs (PowerShell)

### One batch request (correct)

```powershell
$curlArgs = @("-X", "POST", "http://localhost:8000/start")
Get-ChildItem "C:\github_personal\celery-practise\resumes\*.pdf" | ForEach-Object {
    $curlArgs += "-F"
    $curlArgs += ('files=@"{0}"' -f $_.FullName)
}
& curl.exe @curlArgs
```

Paths with spaces (e.g. `Rahul A Gowda.pdf`) must be quoted — use `files=@"path"`.

### PowerShell gotchas

| Issue | Fix |
|---|---|
| `curl` is an alias for `Invoke-WebRequest` | Use `curl.exe` for Unix-style flags |
| `-Parallel` not supported | You're on PowerShell 5.1 — don't use `-Parallel` |
| `file=` vs `files=` | API expects **`files`** (plural) |
| Loop of `/start` calls | Won't show batch timing — use **one request** with all files |

### Swagger UI

Open **http://localhost:8000/docs** → `POST /start` → upload multiple PDFs.

---

## 11. Scaling Workers

Two layers that can be combined:

### Option 1 — Autoscale (within one worker)

```bash
celery -A tasks worker --autoscale=10,1 -n worker@%h
```

- Scales child processes between **min 1** and **max 10** per worker
- Requires **prefork** on Linux/Docker
- Fast response to load spikes on one machine

### Option 2 — Horizontal scaling (more worker instances)

```powershell
# Terminal 1
python -m celery -A tasks worker --pool=threads --concurrency=4 -n worker1@%h

# Terminal 2
python -m celery -A tasks worker --pool=threads --concurrency=4 -n worker2@%h
```

- Each worker is a separate process
- Both pull from the same Redis queue
- Use **unique names** (`-n worker1@%h`, `-n worker2@%h`)
- Total capacity: `workers × concurrency`

### Using both together

```bash
docker compose up --scale worker=3
# Each container: celery -A tasks worker --autoscale=10,1
```

3 workers × (1–10 processes) = **3–30** concurrent tasks.

### When to add workers

- Queue keeps growing under load
- Tasks wait too long before starting
- You want redundancy if one worker crashes

---

## 12. Calculating Workers & Concurrency

### Concurrency per worker

| Task type | Formula |
|---|---|
| CPU-bound | `concurrency ≈ CPU cores` |
| I/O-bound (PDFs, APIs) | `concurrency = cores × 2 to 5` |

PDF extraction is **I/O-bound** — you can exceed core count.

### Total parallelism

```
total_parallel_tasks = workers × concurrency_per_worker
```

### Examples (8-core machine)

| Setup | Total parallel tasks |
|---|---|
| 1 worker × concurrency 16 | 16 |
| 2 workers × concurrency 8 | 16 |
| 3 workers × autoscale 10,1 | 3–30 |

### Rules of thumb

1. Start with `1 worker`, `concurrency = cores` (or 2× for I/O)
2. Watch the queue — if tasks pile up, increase concurrency or add workers
3. Don't exceed memory or DB connection limits
4. Measure with your real workload

---

## 13. Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `The module tasks was not found` | Running from project root | `cd celery` first |
| `Connection closed by server` (Redis) | Wrong port mapping `8231:8231` | Use `8231:6379` in docker-compose |
| `Parameter name 'X' not found` | PowerShell `curl` alias | Use `curl.exe` |
| `ForEach-Object -Parallel` fails | PowerShell 5.1 | Remove `-Parallel` or upgrade to PS 7 |
| `curl: try 'curl --help'` | Paths with spaces unquoted | Use `files=@"path"` |
| Batch time not printing | Hitting `/start` in a loop with `file=` | One request, field `files`, all PDFs attached |
| Prefork issues on Windows | No `fork()` on Windows | Use `--pool=threads` |

---

## Quick Reference

```powershell
# Start everything
cd celery
docker compose up -d
python -m celery -A tasks worker --loglevel=info --pool=threads --concurrency=8 -n worker1@%h
python -m uvicorn app:app --reload

# Upload all resumes
$curlArgs = @("-X", "POST", "http://localhost:8000/start")
Get-ChildItem "..\resumes\*.pdf" | ForEach-Object {
    $curlArgs += "-F"; $curlArgs += ('files=@"{0}"' -f $_.FullName)
}
& curl.exe @curlArgs
```

---

## Mental Model

Think of Celery like a **restaurant**:

- **FastAPI** = waiter (takes orders, doesn't cook)
- **Redis** = order ticket rail (holds pending orders)
- **Worker** = kitchen (does the cooking)
- **Result backend** = pass window (finished plates waiting for pickup)

The waiter never waits for food. They hand the ticket to the rail and move on.

---

## What to Explore Next

- `GET /status/{task_id}` — poll task status without blocking
- Celery Beat — scheduled/cron tasks
- Task retries — `@celery.task(bind=True, max_retries=3)`
- Separate queues — route heavy vs light tasks to different workers
- Docker Compose — run workers in containers with `--scale worker=N`
- KEDA on Kubernetes — auto-scale workers based on queue length
