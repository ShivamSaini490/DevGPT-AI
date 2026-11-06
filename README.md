# DevGPT-AI

Think It. Say It. DevGPT Replies.

DevGPT is a FastAPI application with a static HTML/CSS/JavaScript frontend,
PostgreSQL + pgvector storage, document search, tools, and streamed chat.

## Run FastAPI locally

This project uses Python 3.12. From the repository root, create and activate
the backend virtual environment, install its dependencies, and then run the
exact Uvicorn command below. Do not use a global Python 3.14 `uvicorn`.

```powershell
py -3.12 -m venv backend/venv       # First setup only
.\backend\venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
uvicorn main:app --reload
```

When activation succeeds, the PowerShell prompt begins with `(venv)`. The
local Uvicorn default is <http://127.0.0.1:8000>. PostgreSQL must be available
using `backend/.env`; the Docker database provides it on port `5435`.

The same command also works when your terminal is already inside `backend/`:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

## Run with Docker

Requirements: Git and Docker Desktop (or Docker Engine with Compose).

```powershell
git clone <repository-url>
cd DevGPT-AI
python backend/scripts/setup_local_secrets.py
```

Add your own API keys to `backend/.env`, then start the application:

```powershell
docker compose up --build -d
docker compose ps
```

Open <http://localhost:8080>. API documentation is at
<http://localhost:8080/docs>.

For live reload while editing the backend or the included frontend:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for frontend-developer workflow,
testing, configuration, troubleshooting, and data-management commands.
