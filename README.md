# Universal Media & Video Downloader

A modern, full-stack web application for downloading video and audio content by copy-pasting links from YouTube, Instagram, TikTok, X/Twitter, Facebook, Reddit, and 1000+ supported platforms.

## Features

- **Multi-Platform Support**: Paste links from YouTube, Instagram, TikTok, X/Twitter, Facebook, Reddit, Twitch, Vimeo, etc.
- **Quality & Format Selection**:
  - Video (MP4) with custom resolutions: 4K (2160p), 1440p, 1080p, 720p, 480p, 360p.
  - Audio Only (MP3 / M4A).
- **Real-Time Download Tracking**: Live progress bar, download speed (MB/s), and estimated time remaining (ETA).
- **Glassmorphism Dark UI**: Modern responsive design with smooth animations.
- **Direct Save**: One-click download button to save media directly to your device.
- **Session History**: Track and re-download media from your current session.

## Quick Start

1. Double-click `run.bat` or run in terminal:
   ```cmd
   venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. Open your web browser and navigate to:
   [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Tech Stack

- **Backend**: Python 3, FastAPI, `yt-dlp`, `static-ffmpeg`, Uvicorn.
- **Frontend**: HTML5, CSS3 (Glassmorphism & CSS Variables), Vanilla JavaScript, FontAwesome 6 icons.
