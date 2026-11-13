from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.api import campaigns, streams
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров API
app.include_router(campaigns.router)
app.include_router(streams.router)

BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
def read_root():
    """Главная страница — отдает SPA-интерфейс напрямую."""
    html_file = BASE_DIR / "templates" / "index.html"
    return FileResponse(html_file)

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}