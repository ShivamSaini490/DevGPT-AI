from fastapi.templating import Jinja2Templates

from app.core.paths import FRONTEND_DIR


templates = Jinja2Templates(directory=str(FRONTEND_DIR))
