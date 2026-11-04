
#!/usr/bin/env python3
"""Aggiorna NBA Recap usando le playlist ufficiali NBA."""

import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "catalog.json"

PLAYLISTS = {
    "nightly_recap": "https://www.youtube.com/playlist?list=PLaMWIRum7wA0",
    "game_recap": "https://www.youtube.com/playlist?list=PLftRqjkDhxkg",
}

TEAMS = {
    "Hawks": ["hawks", "atlanta"],
    "Celtics": ["celtics", "boston"],
    "Nets": ["nets", "brooklyn"],
    "Hornets": ["hornets", "charlotte"],
    "Bulls": ["bulls", "chicago"],
    "Cavaliers": ["cavaliers", "cavs", "cleveland"],
    "Mavericks": ["mavericks", "mavs", "dallas"],
    "Nuggets": ["nuggets", "denver"],
    "Pistons": ["pistons", "detroit"],
    "Warriors": ["warriors", "golden state"],
    "Rockets": ["rockets", "houston"],
    "Pacers": ["pacers", "indiana"],
    "Clippers": ["clippers", "la clippers"],
    "Lakers": ["lakers", "los angeles lakers"],
    "Grizzlies": ["grizzlies", "memphis"],
    "Heat": ["heat", "miami"],
    "Bucks": ["bucks", "milwaukee"],
    "Timberwolves": ["timberwolves", "wolves", "minnesota"],
    "Pelicans": ["pelicans", "new orleans"],
    "Knicks": ["knicks", "new york"],
    "Thunder": ["thunder", "oklahoma city", "okc"],
    "Magic": ["magic", "orlando"],
    "76ers": ["76ers", "sixers", "philadelphia"],
    "Suns": ["suns", "phoenix"],
    "Trail Blazers": ["trail blazers", "blazers", "portland"],
    "Kings": ["kings", "sacramento"],
    "Spurs": ["spurs", "san antonio"],
    "Raptors": ["raptors", "toronto"],
    "Jazz": ["jazz", "utah"],
    "Wizards": ["wizards", "washington"],
}

MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December",
        ],
        1,
    )
}


def matches(title, words):
    return any(
        re.search(
            r"(?<!\w)" + re.escape(word) + r"(?!\w)",
            title,
            re.I,
        )
        for word in words
    )


def get_teams(title, content_type):
    if content_type != "game_recap":
        return []

    # Consideriamo soltanto la parte prima di
    # FULL GAME HIGHLIGHTS.
    matchup = re.split(
        r"\|\s*FULL GAME HIGHLIGHTS",
        title,
        maxsplit=1,
        flags=re.I,
    )[0]

    return [
        name
        for name, aliases in TEAMS.items()
        if matches(matchup, aliases)
    ]


def get_published_at(video, title, previous=None):
    # Conserva la data originale dei video già presenti.
    if previous and previous.get("publishedAt"):
        return previous["publishedAt"]

    timestamp = video.get("timestamp")
    if timestamp:
        return dt.datetime.fromtimestamp(
            timestamp, dt.timezone.utc
        ).isoformat()

    upload_date = video.get("upload_date")
    if upload_date and re.fullmatch(r"\d{8}", str(upload_date)):
        date = dt.datetime.strptime(
            str(upload_date), "%Y%m%d"
        ).replace(tzinfo=dt.timezone.utc)
        return date.isoformat()

    # Le playlist flat potrebbero non fornire la data.
    # Usiamo la data della partita indicata nel titolo.
    match = re.search(
        r"\b(" + "|".join(MONTHS) +
        r")\s+(\d{1,2}),?\s+(\d{4})\b",
        title,
        re.I,
    )

    if match:
        month = MONTHS[match.group(1).lower()]
        day = int(match.group(2))
        year = int(match.group(3))

        # Data stimata di pubblicazione: mattina
        # successiva alla partita, ore 08:00 UTC.
        game_date = dt.datetime(
            year, month, day, 8, 0,
            tzinfo=dt.timezone.utc,
        )
        return (
            game_date + dt.timedelta(days=1)
        ).isoformat()

    # Non inventiamo una data per video sconosciuti.
    return None


def fetch_playlist(name, url):
    for attempt in range(1, 4):
        try:
            command = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--flat-playlist",
                "--playlist-end", "500",
                "--dump-single-json",
                "--no-warnings",
                url,
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr[-800:] or "Errore yt-dlp"
                )

            data = json.loads(result.stdout)
            entries = [
                item for item in data.get("entries", [])
                if isinstance(item, dict)
                and item.get("id")
            ]

            if not entries:
                raise ValueError("Playlist vuota")

            print(
                f"OK: {name}: {len(entries)} video",
                flush=True,
            )
            return entries

        except (
            subprocess.TimeoutExpired,
            RuntimeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"ATTENZIONE: {name}, tentativo "
                f"{attempt}/3: {exc}",
                flush=True,
            )

            if attempt < 3:
                time.sleep(5 * attempt)

    return None


def main():
    old = {}

    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
        old = {
            item["videoId"]: item
            for item in data.get("items", [])
            if item.get("videoId")
        }

    # Conserviamo i recap precedenti, escludendo
    # gli Shorts e i contenuti generici del vecchio feed.
    catalog = {
        video_id: item
        for video_id, item in old.items()
        if item.get("contentType")
        in ("nightly_recap", "game_recap")
    }

    added = 0
    successful = 0

    for content_type, url in PLAYLISTS.items():
        entries = fetch_playlist(content_type, url)

        if entries is None:
            print(
                f"ATTENZIONE: {content_type} non disponibile. "
                "Video precedenti conservati.",
                flush=True,
            )
            continue

        successful += 1

        for video in entries:
            video_id = str(video.get("id", ""))
            title = video.get("title") or ""

            if not re.fullmatch(r"[\w-]{11}", video_id):
                continue

            previous = catalog.get(video_id) or old.get(video_id)
            published = get_published_at(
                video, title, previous
            )

            if not published:
                continue

            if video_id not in catalog:
                added += 1

            catalog[video_id] = {
                "videoId": video_id,
                "title": title,
                "publishedAt": published,
                "videoUrl": (
                    "https://www.youtube.com/watch?v="
                    + video_id
                ),
                "source": "NBA (YouTube ufficiale)",
                "contentType": content_type,
                "teams": get_teams(title, content_type),
            }

    if successful == 0:
        print(
            "ATTENZIONE: entrambe le playlist non "
            "disponibili. Catalogo originale conservato."
        )
        return

    items = sorted(
        catalog.values(),
        key=lambda item: item.get("publishedAt", ""),
        reverse=True,
    )[:2500]

    payload = {
        "generatedAt": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "items": items,
    }

    OUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        f"OK: playlist riuscite {successful}/2; "
        f"nuovi {added}; totale {len(items)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
