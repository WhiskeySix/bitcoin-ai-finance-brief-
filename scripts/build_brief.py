import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser

ROOT = Path(__file__).resolve().parents[1]
FEEDS_PATH = ROOT / "feeds.json"
OUT_DIR = ROOT / "briefs"

MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "10"))
MAX_ITEMS_PER_CATEGORY = int(os.getenv("MAX_ITEMS_PER_CATEGORY", "7"))
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))

BLOCK_TITLE_KEYWORDS = [
    "Earnings Call Summary",
    "Earnings Call Transcript",
    "Transcript:",
]

def clean_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def parse_datetime(entry) -> str:
    dt = None
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                break
            except Exception:
                pass
    if not dt:
        return ""
    return dt.isoformat().replace("+00:00", "Z")

def within_days(published_iso: str, days_back: int) -> bool:
    if not published_iso:
        return True
    try:
        dt = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).days <= days_back
    except Exception:
        return True

def normalize_category_name(cat_name: str) -> str:
    pretty = cat_name.replace("_", " ").title()
    pretty = pretty.replace("Ai", "AI").replace("Rwa", "RWA").replace("Btc", "BTC")
    return pretty

def load_feeds():
    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_feed(url: str):
    return feedparser.parse(
        url,
        agent="Mozilla/5.0 (compatible; BriefBot/1.0; +https://github.com)"
    )

def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_feeds()

    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{date_str}.md"

    seen = set()
    md = []
    md.append(f"# Daily Brief — Bitcoin • AI • Finance ({date_str})\n")
    md.append(f"_Generated: {now_utc.isoformat().replace('+00:00','Z')}_\n")
    md.append(f"_Window: last {DAYS_BACK} days • Top {MAX_ITEMS_PER_CATEGORY} per category_\n")

    for cat in data.get("categories", []):
        cat_name = cat.get("name", "uncategorized")
        feeds = sorted(cat.get("feeds", []), key=lambda x: x.get("priority", 99))

        items = []
        for feed in feeds:
            parsed = fetch_feed(feed.get("url", ""))
            entries = getattr(parsed, "entries", [])[:MAX_ITEMS_PER_FEED]

            for e in entries:
                title = clean_text(getattr(e, "title", ""))
                link = clean_text(getattr(e, "link", ""))
                if not title or not link:
                    continue

                if any(k.lower() in title.lower() for k in BLOCK_TITLE_KEYWORDS):
                    continue

                pub = parse_datetime(e)
                if pub and not within_days(pub, DAYS_BACK):
                    continue

                key = (link.lower(), title.lower())
                if key in seen:
                    continue
                seen.add(key)

                items.append({
                    "title": title,
                    "link": link,
                    "domain": domain(link),
                    "published": pub,
                })

        if not items:
            continue

        dated = [i for i in items if i["published"]]
        undated = [i for i in items if not i["published"]]
        dated.sort(key=lambda x: x["published"], reverse=True)
        undated.sort(key=lambda x: (x["domain"], x["title"].lower()))
        items = (dated + undated)[:MAX_ITEMS_PER_CATEGORY]

        pretty_cat = normalize_category_name(cat_name)
        md.append(f"## {pretty_cat}\n")

        for it in items:
            meta = it["domain"] or "source"
            if it["published"]:
                meta += f" • {it['published'][:10]}"
            md.append(f"- [{it['title']}]({it['link']}) — _{meta}_")
        md.append("")

    out_path.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")

if __name__ == "__main__":
    build()
