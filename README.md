# DevGPT-AI

Think It. Say It. DevGPT Replies.

DevGPT is a FastAPI application with a React + Vite frontend,
PostgreSQL + pgvector storage, document search, tools, and streamed chat.

## Chat "+" menu

The **+** button in the composer offers:

| Option | What it does | Needs |
| --- | --- | --- |
| Add photos & files | Attach images (read by a vision model) and documents (indexed for search). Paste or drag-and-drop also work. | `GROQ_API_KEY`, `GOOGLE_API_KEY` for documents |
| Add from library | Re-attach any file from your earlier chats | — |
| Create image | Generates an image from your description | `IMAGE_GENERATION_URL` (free default) |
| Web search | Always searches the web and cites sources | `TAVILY_API_KEY` |
| Work in a project | Groups chats; project instructions apply to every chat in it | — |
| Deep research | Several searches, then a structured report with sources | `TAVILY_API_KEY` |
| Sketch | Draw on a canvas and attach the drawing | — |
| Thinking | Higher reasoning effort; the thought process is shown separately | — |
| GitHub | Triage PRs and issues, check CI, publish issues/comments | `GITHUB_TOKEN` (optional for public read-only) |
| Figma | Read a Figma file and turn it into code, or design from scratch | `FIGMA_TOKEN` |

See `backend/.env.example` for these settings.

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

For live reload while editing the backend or the frontend:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

The Vite dev server then runs at <http://localhost:5173> with hot reload.

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for frontend-developer workflow,
testing, configuration, troubleshooting, and data-management commands.
