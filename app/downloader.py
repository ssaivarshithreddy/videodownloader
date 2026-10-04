import os
import uuid
import tempfile
import threading
import logging
import yt_dlp
import static_ffmpeg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Safely initialize static ffmpeg without crashing on read-only file systems (like Vercel)
try:
    static_ffmpeg.add_paths()
except Exception as e:
    logger.warning(f"Static ffmpeg path initialization skipped: {e}")

# Determine a writable download directory.
# Vercel and AWS Lambda serverless environments have a read-only filesystem except for /tmp.
try:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(base_dir, "downloads")
    os.makedirs(target_dir, exist_ok=True)
    
    # Verify write access by attempting to create and remove a test file
    test_file = os.path.join(target_dir, ".perm_test")
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
    
    DOWNLOAD_DIR = target_dir
except Exception:
    DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "downloads")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger.info(f"Using DOWNLOAD_DIR: {DOWNLOAD_DIR}")

# Global dictionary to track active task progress
tasks_progress = {}

def get_yt_dlp_options(download: bool = False, output_template: str = None, client_list: list = None):
    """
    Returns optimized yt-dlp options bypassing YouTube bot detection & cloud IP blocks.
    Strictly uses mobile Android & iOS API clients to bypass web bot verification.
    """
    clients = client_list or ['android', 'ios']
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': not download,
        'nocheckcertificate': True,
        'user_agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11; US) gzip',
        'extractor_args': {
            'youtube': {
                'player_client': clients
            }
        }
    }

    # Optional: Use cookies.txt if provided in root folder or via environment variable
    cookies_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cookies.txt')
    if os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
    elif os.environ.get("YOUTUBE_COOKIES"):
        try:
            tmp_cookies = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
            with open(tmp_cookies, "w", encoding="utf-8") as f:
                f.write(os.environ.get("YOUTUBE_COOKIES"))
            opts['cookiefile'] = tmp_cookies
        except Exception as ce:
            logger.warning(f"Could not write cookies env var: {ce}")

    if output_template:
        opts['outtmpl'] = output_template
    return opts

def get_video_info(url: str):
    """
    Extracts metadata, thumbnails, and available format options for a given video URL.
    Supports YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit, etc.
    """
    # Primary attempt using Android + iOS native app clients
    ydl_opts = get_yt_dlp_options(download=False, client_list=['android', 'ios'])
    
    info = None
    last_err = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        last_err = e
        logger.warning(f"Primary yt-dlp android+ios extract failed: {e}. Trying fallback clients...")
        
        # Fallback 1: Try iOS client specifically
        try:
            fallback_opts = get_yt_dlp_options(download=False, client_list=['ios'])
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as fb_err1:
            last_err = fb_err1
            # Fallback 2: Try Android Creator client
            try:
                fallback_opts2 = get_yt_dlp_options(download=False, client_list=['android_creator'])
                with yt_dlp.YoutubeDL(fallback_opts2) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as fb_err2:
                last_err = fb_err2

    if not info:
        raise ValueError(f"Failed to fetch video details: {str(last_err)}")

    if 'entries' in info and info['entries']:
        # Playlist or multi-video link, take the first valid entry
        info = info['entries'][0]

    title = str(info.get('title') or 'Unknown Title')
    duration = info.get('duration')
    duration_str = format_duration(duration) if duration else 'N/A'
    
    thumbnail = None
    if info.get('thumbnail'):
        thumbnail = str(info['thumbnail'])
    elif info.get('thumbnails') and len(info['thumbnails']) > 0:
        thumbnail = str(info['thumbnails'][-1].get('url', ''))

    uploader = str(info.get('uploader') or info.get('channel') or info.get('extractor_key') or 'Unknown')
    extractor = str(info.get('extractor_key') or 'Unknown')

    # Process format choices
    video_formats = [{
        'format_id': 'bestvideo+bestaudio/best',
        'label': 'Best Available Quality (Auto MP4)',
        'ext': 'mp4',
        'quality': 'Best'
    }]

    seen_resolutions = set()
    raw_formats = info.get('formats', []) or []
    
    # Sort and collect common video resolutions
    for f in raw_formats:
        vcodec = f.get('vcodec', 'none')
        height = f.get('height')
        ext = str(f.get('ext', 'mp4'))

        if vcodec != 'none' and height and height not in seen_resolutions:
            seen_resolutions.add(height)
            video_formats.append({
                'format_id': f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                'label': f"{height}p ({ext.upper()})",
                'ext': 'mp4',
                'quality': f"{height}p"
            })

    # Sort video formats descending by height where possible
    if len(video_formats) > 1:
        video_formats[1:] = sorted(
            video_formats[1:],
            key=lambda x: int(x['quality'].replace('p', '')) if x['quality'].replace('p', '').isdigit() else 0,
            reverse=True
        )

    audio_formats = [
        {'format_id': 'bestaudio/best', 'label': 'Best Audio (MP3)', 'ext': 'mp3', 'quality': '320kbps'},
        {'format_id': 'bestaudio/best', 'label': 'Audio Only (M4A)', 'ext': 'm4a', 'quality': 'Best'}
    ]

    return {
        'url': str(url),
        'title': title,
        'duration': duration_str,
        'duration_seconds': duration if isinstance(duration, (int, float)) else None,
        'thumbnail': thumbnail,
        'uploader': uploader,
        'platform': extractor,
        'video_formats': video_formats,
        'audio_formats': audio_formats
    }

def format_duration(seconds) -> str:
    if not seconds:
        return 'N/A'
    try:
        sec = int(seconds)
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except Exception:
        return 'N/A'

def start_download_task(url: str, format_id: str, format_type: str = 'video') -> str:
    """
    Spawns a background thread to download the requested video/audio and returns a task_id.
    """
    task_id = str(uuid.uuid4())
    tasks_progress[task_id] = {
        'task_id': task_id,
        'status': 'starting',
        'percentage': 0.0,
        'speed': '0 KB/s',
        'eta': '--:--',
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'filename': '',
        'filepath': '',
        'error': None
    }

    thread = threading.Thread(target=_download_worker, args=(task_id, url, format_id, format_type), daemon=True)
    thread.start()
    return task_id

def _download_worker(task_id: str, url: str, format_id: str, format_type: str):
    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percentage = (downloaded / total * 100) if total > 0 else 0.0
            
            speed_bytes = d.get('speed') or 0
            speed_str = format_speed(speed_bytes)
            
            eta = d.get('eta')
            eta_str = f"{eta}s" if eta is not None else "--:--"

            tasks_progress[task_id].update({
                'status': 'downloading',
                'percentage': round(percentage, 1),
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': speed_str,
                'eta': eta_str
            })
        elif d['status'] == 'finished':
            tasks_progress[task_id].update({
                'status': 'processing',
                'percentage': 99.0,
                'filename': os.path.basename(d.get('filename', '')),
                'filepath': d.get('filename', '')
            })

    output_template = os.path.join(DOWNLOAD_DIR, '%(title).100s_%(id)s.%(ext)s')
    ydl_opts = get_yt_dlp_options(download=True, output_template=output_template, client_list=['android', 'ios'])
    ydl_opts['progress_hooks'] = [progress_hook]

    if format_type == 'audio':
        ext = 'mp3' if 'mp3' in format_id or format_id == 'bestaudio/best' else 'm4a'
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': ext,
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': format_id if format_id else 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Adjust filename extension if post-processed
            if format_type == 'audio':
                base, _ = os.path.splitext(filename)
                target_ext = 'mp3' if 'mp3' in format_id or format_id == 'bestaudio/best' else 'm4a'
                possible_file = f"{base}.{target_ext}"
                if os.path.exists(possible_file):
                    filename = possible_file
            elif not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                if os.path.exists(f"{base}.mp4"):
                    filename = f"{base}.mp4"

            tasks_progress[task_id].update({
                'status': 'completed',
                'percentage': 100.0,
                'filename': os.path.basename(filename),
                'filepath': filename
            })
    except Exception as e:
        logger.error(f"Download worker error for task {task_id}: {e}")
        tasks_progress[task_id].update({
            'status': 'failed',
            'error': str(e)
        })

def format_speed(bytes_per_sec) -> str:
    if not bytes_per_sec:
        return '0 KB/s'
    if bytes_per_sec >= 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
    elif bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec} B/s"

def get_task_status(task_id: str):
    return tasks_progress.get(task_id, {'status': 'not_found'})
