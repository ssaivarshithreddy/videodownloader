@echo off
echo Starting Universal Video Downloader App...
call venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
