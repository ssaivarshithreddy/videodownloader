import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl

from app.downloader import (
    get_video_info,
    start_download_task,
    get_task_status,
    DOWNLOAD_DIR
)

app = FastAPI(
    title="Universal Video & Media Downloader",
    description="Download videos and audio from YouTube, Instagram, TikTok, Twitter/X, Facebook, and more.",
    version="1.0.0"
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    format_type: str = "video"  # "video" or "audio"

@app.post("/api/info")
async def fetch_info(req: InfoRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    try:
        info = get_video_info(req.url.strip())
        return JSONResponse(content=info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def trigger_download(req: DownloadRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    try:
        task_id = start_download_task(req.url.strip(), req.format_id, req.format_type)
        return JSONResponse(content={"task_id": task_id, "status": "started"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# Serve UI frontend static files
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
