#!/usr/bin/env python3
"""Collect official NBA YouTube uploads, preserving previously seen items."""
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UCWJ2lWNubArHWmf3FIHbfcQ"
OUT = Path(__file__).resolve().parents[1] / "catalog.json"
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
TEAMS = {
    "Hawks": ["hawks", "atlanta"], "Celtics": ["celtics", "boston"],
    "Nets": ["nets", "brooklyn"], "Hornets": ["hornets", "charlotte"],
    "Bulls": ["bulls", "chicago"], "Cavaliers": ["cavaliers", "cavs", "cleveland"],
    "Mavericks": ["mavericks", "mavs", "dallas"], "Nuggets": ["nuggets", "denver"],
    "Pistons": ["pistons", "detroit"], "Warriors": ["warriors", "golden state"],
    "Rockets": ["rockets", "houston"], "Pacers": ["pacers", "indiana"],
    "Clippers": ["clippers", "la clippers"], "Lakers": ["lakers", "los angeles lakers"],
    "Grizzlies": ["grizzlies", "memphis"], "Heat": ["heat", "miami"],
    "Bucks": ["bucks", "milwaukee"], "Timberwolves": ["timberwolves", "wolves", "minnesota"],
    "Pelicans": ["pelicans", "new orleans"], "Knicks": ["knicks", "new york"],
    "Thunder": ["thunder", "oklahoma city", "okc"], "Magic": ["magic", "orlando"],
    "76ers": ["76ers", "sixers", "philadelphia"], "Suns": ["suns", "phoenix"],
    "Trail Blazers": ["trail blazers", "blazers", "portland"], "Kings": ["kings", "sacramento"],
    "Spurs": ["spurs", "san antonio"], "Raptors": ["raptors", "toronto"],
    "Jazz": ["jazz", "utah"], "Wizards": ["wizards", "washington"],
}


def matches(title, words):
    return any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", title, re.I) for word in words)


def classify(title):
    t = title.lower()
    if "nightly recap" in t:
        return "nightly_recap"
    if "full game highlights" in t or "game highlights" in t or "full game recap" in t:
        return "game_recap"
    if "highlights" in t or "recap" in t:
        return "highlights"
    return "other"


def fetch_entries():
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(FEED, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NBARecap/1.0; RSS reader)",
                "Accept": "application/atom+xml, application/xml, text/xml, */*",
            })
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read()
            entries = ET.fromstring(body).findall(f"{ATOM}entry")
            if not entries:
                raise ValueError("Feed NBA vuoto: nessun video ricevuto")
            return entries
        except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError, ValueError) as exc:
            print(f"ATTENZIONE: tentativo {attempt}/3 fallito: {exc}", flush=True)
            if attempt < 3:
                time.sleep(5 * attempt)
    return None


def main():
    entries = fetch_entries()
    if entries is None:
        print("ATTENZIONE: YouTube non disponibile. Catalogo precedente conservato; riprovare più tardi.")
        return

    old = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
        old = {v["videoId"]: v for v in data.get("items", []) if v.get("videoId")}

    added = 0
    for entry in entries:
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title") or ""
        published = entry.findtext(f"{ATOM}published")
        if not video_id or not published:
            continue
        if video_id not in old:
            added += 1
        old[video_id] = {
            "videoId": video_id,
            "title": title,
            "publishedAt": published,
            "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
            "source": "NBA (YouTube ufficiale)",
            "contentType": classify(title),
            "teams": [name for name, aliases in TEAMS.items() if matches(title, aliases)],
        }

    items = sorted(old.values(), key=lambda v: v.get("publishedAt", ""), reverse=True)[:2500]
    payload = {"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: feed {len(entries)} video; nuovi {added}; totale {len(items)}")


if __name__ == "__main__":
    main()
