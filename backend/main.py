"""Backend ASGI entrypoint for ``uvicorn main:app --reload``."""

import sys


if sys.version_info[:2] != (3, 12):
    raise RuntimeError(
        "DevGPT requires Python 3.12. Activate backend/venv before running "
        "`uvicorn main:app --reload`."
    )

from app.main import app


__all__ = ["app"]
