import os
import logging
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.downloader import (
    get_video_info,
    start_download_task,
    get_task_status,
    DOWNLOAD_DIR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Universal Video & Media Downloader",
    description="Download videos and audio from YouTube, Instagram, TikTok, Twitter/X, Facebook, and more.",
    version="1.0.0"
)

# Enable CORS for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    format_type: str = "video"  # "video" or "audio"

@app.get("/", response_class=FileResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.post("/api/info")
async def fetch_info(req: InfoRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    try:
        info = get_video_info(req.url.strip())
        return JSONResponse(content=info)
    except ValueError as ve:
        logger.warning(f"Validation error in /api/info: {ve}")
        return JSONResponse(status_code=400, content={"detail": str(ve)})
    except Exception as e:
        logger.error(f"Unexpected error in /api/info: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": f"Server error: {str(e)}"})

@app.post("/api/download")
async def trigger_download(req: DownloadRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    try:
        task_id = start_download_task(req.url.strip(), req.format_id, req.format_type)
        return JSONResponse(content={"task_id": task_id, "status": "started"})
    except Exception as e:
        logger.error(f"Error in /api/download: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/progress/{task_id}")
async def check_progress(task_id: str):
    status_data = get_task_status(task_id)
    if status_data.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task ID not found")
    return JSONResponse(content=status_data)

@app.get("/api/file/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file not found")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")

# Mount static files directory if it exists
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
