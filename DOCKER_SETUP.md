# DevGPT Docker development environment

This repository runs as two containers:

- `backend`: FastAPI/Uvicorn on port `8080`; it also serves the current static frontend.
- `postgres`: PostgreSQL 16 with pgvector 0.8.7 on host port `5435`.

The setup is intended for local development and testing. It is not a hardened
production deployment.

## First setup after cloning

Install Git, Python 3, and Docker Desktop (or Docker Engine + Compose). Then:

```powershell
git clone <repository-url>
cd DevGPT-AI
python backend/scripts/setup_local_secrets.py
```

The helper creates `backend/.env` from `backend/.env.example`, generates a
unique `SECRET_KEY` and `POSTGRES_PASSWORD`, and does not print either value.
Existing real values are preserved when the command is run again.

Open `backend/.env` and add the API keys you are authorized to use. At minimum,
chat requires `GROQ_API_KEY`. Other keys enable their related features:

- `GOOGLE_API_KEY`: document embeddings
- `TAVILY_API_KEY`: web/place search
- `WEATHER_API_KEY`: WeatherAPI weather data
- `ALPHA_VANTAGE_API_KEY`: stock data
- `LANGSMITH_API_KEY`: optional tracing when `LANGSMITH_TRACING=true`

Never commit `backend/.env` or send it to another developer. Every developer
creates their own file and uses their own authorized credentials. The file is
excluded by both Git and the Docker build context.

Start the project:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 backend
```

Open:

- App: <http://localhost:8080>
- FastAPI docs: <http://localhost:8080/docs>
- PostgreSQL from the host: `127.0.0.1:5435`
- PostgreSQL between containers: `postgres:5432`

Compose waits for PostgreSQL to become healthy before starting FastAPI. The
backend creates the `vector` extension and application tables on startup.

## Daily development

Use the development overlay to bind-mount both source directories and enable
Uvicorn reload:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Backend Python changes restart Uvicorn. HTML, CSS, and JavaScript changes are
visible after refreshing the browser. Stop with `Ctrl+C`, or run detached with
`-d` and later use the same file arguments with `down`:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml down
```

Useful commands:

```powershell
# Follow application and database logs
docker compose logs -f backend postgres

# Rebuild after changing Python dependencies or the Dockerfile
docker compose up --build -d

# Stop containers but keep database and uploads
docker compose down

# Show resolved Compose configuration without exposing env-file values
docker compose config --quiet
```

Do not use `docker compose down -v` during routine work. The `-v` flag deletes
the named database and upload volumes.

## Frontend developer workflow

The checked-in `frontend/` directory is served by FastAPI, so a frontend
developer can edit it immediately with the development command above. Browser
requests use relative URLs and reach the backend at the same origin.

If a separate React/Vite frontend is introduced, run it on port `5173` and use
`http://localhost:8080` as its API base URL. The default backend CORS list
already allows:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Each browser client must continue to follow the API's `X-Client-Id` and
streaming contracts.

## Run tests in Docker

The test stack uses a disposable PostgreSQL/pgvector database. It never uses
the development database or real API keys.

```powershell
docker compose -f compose.test.yaml --profile tests up --build `
  --abort-on-container-exit --exit-code-from backend-tests
docker compose -f compose.test.yaml --profile tests down
```

On Bash/zsh, replace the PowerShell backtick with `\`, or put the command on
one line.

To run pytest from a local Python environment against only the Docker test DB:

```powershell
docker compose -f compose.test.yaml up -d --wait postgres-test
cd backend
python -m pip install -r requirements-dev.txt
pytest
cd ..
docker compose -f compose.test.yaml down
```

## Ports and local overrides

Defaults can be changed with a root `.env` file (also Git-ignored):

```dotenv
BACKEND_PORT=8081
POSTGRES_HOST_PORT=5437
TEST_POSTGRES_HOST_PORT=5438
```

These values only control host port publishing. Do not change the container
database hostname/port; the backend must use `postgres:5432` inside Compose.

## Existing database password mismatch

Changing `POSTGRES_PASSWORD` does not update an already-initialized PostgreSQL
volume. If you deliberately changed the local password and need to update the
existing Compose role, start PostgreSQL and run:

```powershell
python backend/scripts/setup_local_secrets.py --sync-postgres
docker compose restart backend
```

The synchronization command passes SQL through standard input and does not
print the password.

## Environment syntax notes

Use ordinary dotenv syntax:

```dotenv
# This is a comment
GROQ_MODEL=openai/gpt-oss-120b
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Do not include Markdown formatting, trailing backslashes, or `*# comment *`.
Spaces are allowed in values such as `APP_NAME=DevGPT API`, but avoid spaces
around variable names. The current backend uses Google for its fixed embedding
model and Groq for chat; it does not read a `GOOGLE_MODEL` setting.

## Troubleshooting

```powershell
# Check service and health state
docker compose ps

# Inspect startup errors
docker compose logs postgres backend

# Verify backend/.env is ignored by Git
git check-ignore -v backend/.env

# Validate the Compose files
docker compose config --quiet
docker compose -f compose.test.yaml --profile tests config --quiet
```

If port `5435` or `8080` is already occupied, use the port override file above.
If an API-dependent feature fails, confirm that its key is populated and that
the configured provider/model is available to your account.
