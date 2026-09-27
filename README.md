# IS Compliance and Verification Platform

A local-first workspace for reviewing procurement documents against a seeded catalogue of Indian Standards. It combines document extraction, standards search, version/reference and certification checks, evidence-backed recommendations, human review, audit events, and project PDF reports.

> **Read before use:** This is a prototype, not an authoritative compliance decision system. The standards and certification catalogue is limited and requires verification against current BIS publications and applicable orders. A recommendation or relevance score does not establish compliance. See [Production readiness](docs/PRODUCTION_READINESS.md).

## Contents

- [What it does](#what-it-does)
- [Technology](#technology)
- [Run locally](#run-locally)
- [Sign-in and accounts](#sign-in-and-accounts)
- [Run with Docker Compose](#run-with-docker-compose)
- [Tests and quality checks](#tests-and-quality-checks)
- [Data and backups](#data-and-backups)
- [Project status and known limitations](#project-status-and-known-limitations)

## What it does

- Stores projects and tender documents; accepts PDF, DOCX, XLSX, and TXT uploads.
- Extracts text and specification entities. Sparse PDF pages can be rendered with PDFium and read with Tesseract OCR.
- Searches the seeded standards catalogue using exact, keyword, semantic, and hybrid rank-fusion search.
- Checks catalogue versions, amendments, linked references, certification/QCO entries, possible gaps, and potential conflicts.
- Produces deterministic explanations from retrieved evidence. It does not call a generative language model.
- Saves recommendations as pending review, supports reviewer comments and accept/reject decisions, and records audit events.
- Exports project review information and history as a PDF.

The app distinguishes document excerpts from catalogue scope. It does not contain the complete licensed text of BIS standards, and its catalogue is not automatically synchronized with BIS or government sources.

## Technology

- **Frontend:** React 19, Vite, JavaScript, CSS.
- **API:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Database:** PostgreSQL 17 for Compose; SQLite for local development and tests.
- **Search:** SentenceTransformers, NumPy, scikit-learn, and FAISS.
- **Documents:** pypdf, PDFium, Tesseract OCR, python-docx, and openpyxl.
- **Reports and operations:** ReportLab, Docker Compose, GitHub Actions.

## Run locally

### Requirements

- Python 3.13
- Node.js 22 and npm
- Tesseract OCR installed and available on `PATH` to process scanned PDFs. Text-based PDFs and other formats do not require OCR.

### 1. Install backend dependencies

In PowerShell from the repository root:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Create `backend/.env` from `backend/.env.example` if you do not already have one. Keep `.env` local and do not commit it. Set a persistent development `SECRET_KEY` so signing keys do not change when the API restarts; generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `backend/.env` as `SECRET_KEY="..."`. The default database URL is `sqlite:///./data/is_platform.db`; therefore, run backend commands from the `backend` directory.

### 2. Initialize a new local database

Use a fresh database for this first-time bootstrap. `seed_database` skips account creation if roles already exist in the database.

```powershell
$env:BOOTSTRAP_ADMIN_EMAIL = "you@example.com"
$env:BOOTSTRAP_ADMIN_PASSWORD = "<generate-a-unique-password-of-16-to-72-bytes>"
$env:BOOTSTRAP_ADMIN_NAME = "Platform Administrator"

python -m alembic upgrade head
python -c "from app.db.seed import seed_database; seed_database(include_demo_users=False)"
python -c "from app.db.seed_relationships import seed_extended_relationships; seed_extended_relationships()"

Remove-Item Env:BOOTSTRAP_ADMIN_EMAIL, Env:BOOTSTRAP_ADMIN_PASSWORD, Env:BOOTSTRAP_ADMIN_NAME
```

Keep the bootstrap password in a password manager. The seed process creates an administrator and illustrative catalogue data; it does not create public user registration.

If you already have a local database, do not run a fresh-database procedure against it without a backup. Starting the API checks/creates ORM tables, but schema upgrades should be applied explicitly with Alembic.

### 3. Start the API

From `backend`:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check readiness at `http://127.0.0.1:8000/api/v1/health/ready`. Interactive API docs are at `http://127.0.0.1:8000/api/docs` in development mode.
