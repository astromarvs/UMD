import yt_dlp
import os
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests

class Logger(object):
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        
    def debug(self, msg):
        if self.log_callback:
            clean_msg = re.sub(r'\x1b\[[0-9;]*[mK]', '', msg)
            if any(keyword in msg for keyword in [
                "Downloading", "Destination", "Merging", "Extracting", 
                "Finished", "100%", "Subtitles", "Writing"
            ]):
                self.log_callback(f"DEBUG: {clean_msg}")
            
    def info(self, msg):
        if self.log_callback:
            self.log_callback(f"INFO: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")
            
    def warning(self, msg):
        if self.log_callback:
            self.log_callback(f"WARNING: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")
            
    def error(self, msg):
        if self.log_callback:
            self.log_callback(f"ERROR: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")

def _fetch_info(url):
    """Get metadata only (no download)."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None

def _is_image(info):
    """Return True if post is image-like (single photo)."""
    if not info:
        return False
    ext = info.get('ext', '').lower()
    if ext in ['jpg', 'jpeg', 'png', 'webp']:
        return True
    # fallback: check thumbnail or url endings
    thumb = info.get('thumbnail') or info.get('url')
    if thumb and any(thumb.lower().endswith(x) for x in ['.jpg', '.jpeg', '.png', '.webp']):
        return True
    return False

def _download_image(url, path, log_callback=None):
    """Download image directly via requests."""
    if log_callback:
        log_callback(f"Downloading image directly → {os.path.basename(path)}")
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        if log_callback:
            log_callback(f"Saved image → {path}")
    else:
        raise ValueError(f"Failed to download image. HTTP {r.status_code}")

def _strip_playlist(url):
    """Remove any playlist parameters (&list=... or ?list=...) from a YouTube URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if 'list' in query:
        query.pop('list')  # remove playlist id
    if 'index' in query:
        query.pop('index')  # remove playlist index
    clean_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=clean_query))
    return cleaned_url

def download_youtube(url, output_path, filename, fmt, progress_hook, log_callback, subtitle_lang, download_subtitles):
    """Download YouTube video or audio (mp3), ignoring playlists completely."""
    
    # --- Step 1. Clean URL (strip playlist) ---
    url = _strip_playlist(url)
    if log_callback:
        log_callback(f"Sanitized YouTube URL → {url}")

    # --- Step 2. Optional pre-check (for logging only) ---
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get('_type') == 'playlist':
                if log_callback:
                    log_callback("Playlist detected — forcing single video download only.")
    except Exception:
        if log_callback:
            log_callback("Could not verify playlist info — proceeding with noplaylist=True.")

    # --- Step 3. Prepare yt-dlp options ---
    if fmt == "mp3":
        filename = filename or "audio"
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_path, filename),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,  # force single video
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }],
            'logger': Logger(log_callback),
        }
        if download_subtitles and subtitle_lang and subtitle_lang != "none":
            base = os.path.splitext(os.path.join(output_path, filename))[0]
            opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'srt',
                'subtitleslangs': None if subtitle_lang == "all" else [subtitle_lang],
                'outtmpl': {'default': os.path.join(output_path, filename),
                            'subtitle': base + '.%(ext)s'}
            })
    else:
        filename = (filename or "video") + ".mp4"
        opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_path, filename),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,  # force single video
            'logger': Logger(log_callback),
        }
        if download_subtitles:
            if subtitle_lang == "all":
                opts.update({
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitlesformat': 'srt'
                })
            elif subtitle_lang and subtitle_lang != "none":
                opts.update({
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': [subtitle_lang],
                    'subtitlesformat': 'srt'
                })
                
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]

    # --- Step 4. Execute download ---
    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading YouTube → {filename}")
        ydl.download([url])


def download_tiktok(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download TikTok video."""
    # TikTok only supports video format
    filename = (filename or "video") + ".mp4"
    opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_path, filename),
        'quiet': False,
        'no_warnings': False,
        'logger': Logger(log_callback),
        'noplaylist': True
    }
    
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading TikTok → {filename}")
        ydl.download([url])

def download_instagram(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download Instagram content (image or video)."""
    info = _fetch_info(url)
    if not info:
        if log_callback:
            log_callback("Could not fetch info from Instagram URL.")
        return

    if _is_image(info):
        # Direct image download (skip yt-dlp)
        img_url = info.get('url') or info.get('thumbnail')
        ext = fmt if fmt in ['jpg', 'jpeg'] else 'jpg'
        filename = (filename or info.get('title', 'image')) + "." + ext
        image_path = os.path.join(output_path, filename)
        _download_image(img_url, image_path, log_callback)
    else:
        # treat as video
        if fmt == "mp3":
            filename = filename or "audio"
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, filename),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192'
                }],
                'logger': Logger(log_callback),
                'noplaylist': True
            }
        else:
            filename = (filename or "video") + ".mp4"
            opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'merge_output_format': 'mp4',
                'outtmpl': os.path.join(output_path, filename),
                'quiet': False,
                'no_warnings': False,
                'logger': Logger(log_callback),
                'noplaylist': True
            }
        if progress_hook:
            opts['progress_hooks'] = [progress_hook]
        with yt_dlp.YoutubeDL(opts) as ydl:
            if log_callback:
                log_callback(f"Downloading Instagram → {filename}")
            ydl.download([url])

def download_facebook(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download Facebook content (image or video)."""
    info = _fetch_info(url)
    if not info:
        if log_callback:
            log_callback("Could not fetch info from Facebook URL.")
        return

    if _is_image(info):
        # Direct image download (skip yt-dlp)
        img_url = info.get('url') or info.get('thumbnail')
        ext = fmt if fmt in ['jpg', 'jpeg'] else 'jpg'
        filename = (filename or info.get('title', 'image')) + "." + ext
        image_path = os.path.join(output_path, filename)
        _download_image(img_url, image_path, log_callback)
    else:
        # treat as video
        if fmt == "mp3":
            filename = filename or "audio"
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, filename),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192'
                }],
                'logger': Logger(log_callback),
                'noplaylist': True
            }
        else:
            filename = (filename or "video") + ".mp4"
            opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'merge_output_format': 'mp4',
                'outtmpl': os.path.join(output_path, filename),
                'quiet': False,
                'no_warnings': False,
                'logger': Logger(log_callback),
                'noplaylist': True
            }
        if progress_hook:
            opts['progress_hooks'] = [progress_hook]
        with yt_dlp.YoutubeDL(opts) as ydl:
            if log_callback:
                log_callback(f"Downloading Facebook → {filename}")
            ydl.download([url])