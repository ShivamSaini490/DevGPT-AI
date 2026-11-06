"""Repository-level ASGI entrypoint for ``uvicorn main:app --reload``."""

import sys
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise RuntimeError(
        "DevGPT requires Python 3.12. From the repository root run "
        "`.\\backend\\venv\\Scripts\\Activate.ps1`, then run "
        "`uvicorn main:app --reload` again."
    )


BACKEND_DIR = Path(__file__).resolve().parent / "backend"
backend_path = str(BACKEND_DIR)

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app  # noqa: E402


__all__ = ["app"]
