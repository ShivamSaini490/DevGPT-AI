from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
# Production build of the React/Vite app (`npm run build` in frontend/).
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"

UPLOADS_DIR = BACKEND_DIR / "uploads"
ENV_FILE = BACKEND_DIR / ".env"

UPLOADS_DIR.mkdir(exist_ok=True)
