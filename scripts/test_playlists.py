
import json
import subprocess
import sys

PLAYLISTS = {
    "Nightly Recap": "https://www.youtube.com/playlist?list=PLaMWIRum7wA0",
    "Full Game Highlights": "https://www.youtube.com/playlist?list=PLftRqjkDhxkg",
}

for name, url in PLAYLISTS.items():
    print(f"\n=== {name} ===", flush=True)

    result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist",
            "--playlist-end", "5",
            "--dump-single-json",
            "--no-warnings",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )

    if result.returncode != 0:
        print("ERRORE:", result.stderr[-1200:])
        continue

    data = json.loads(result.stdout)
    entries = data.get("entries", [])

    print("Playlist:", data.get("title"))
    print("Video trovati:", len(entries))

    for video in entries:
        print("-", video.get("title"), video.get("id"))
