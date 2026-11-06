from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from app.core.paths import FRONTEND_DIST_DIR


router = APIRouter()

FRONTEND_NOT_BUILT_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>DevGPT</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 640px; margin: 15vh auto; padding: 0 16px;">
  <h1>DevGPT</h1>
  <p>The API is running, but the frontend has not been built.</p>
  <p>Run <code>npm install &amp;&amp; npm run build</code> in <code>frontend/</code>,
     or start the dev server with <code>npm run dev</code> and open
     <a href="http://localhost:5173">http://localhost:5173</a>.</p>
</body>
</html>
"""


@router.get("/")
@router.get("/chat")
async def home():
    """Serve the single-page app; "/" is the landing page, "/chat" the chat."""
    index_file = FRONTEND_DIST_DIR / "index.html"

    if index_file.is_file():
        # index.html references hashed assets, so it must not be cached.
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    return HTMLResponse(FRONTEND_NOT_BUILT_HTML, status_code=200)
