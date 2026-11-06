# DevGPT-AI

Think It. Say It. DevGPT Replies.

DevGPT is a FastAPI application with a React + Vite frontend,
PostgreSQL + pgvector storage, document search, tools, and streamed chat.

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
