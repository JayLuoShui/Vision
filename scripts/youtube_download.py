import yt_dlp

url = "https://www.youtube.com/watch?v=VSHu55q3tE8"

ydl_opts = {
    "format": "bv*[ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best",
    "merge_output_format": "mp4",
    "outtmpl": "%(title)s.%(ext)s",
    "noplaylist": True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
