import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import yt_dlp

opts = {
    "format": "bestvideo[height<=1080]",
    "outtmpl": "yt_dl/%(id)s.%(ext)s",
    "quiet": False,
    "noplaylist": True,
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/watch?v=d8TZhL7dvao", download=True)
    print(f'Title: {info.get("title")}')
    print(f'Duration: {info.get("duration")}s')
    print(f'Resolution: {info.get("width")}x{info.get("height")}')
