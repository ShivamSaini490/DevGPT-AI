from pathlib import Path

import uvicorn


BACKEND_DIR = Path(__file__).resolve().parent


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        app_dir=str(BACKEND_DIR),
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=[str(BACKEND_DIR / "app")],
    )
