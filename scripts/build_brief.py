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

MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "12"))
MAX_ITEMS_PER_CATEGORY = int(os.getenv("MAX_ITEMS_PER_CATEGORY", "25"))

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
    sections_md = []

    sections_md.append(f"# Daily Brief — Bitcoin • AI • Finance ({date_str})\n")
    sections_md.append(f"_Generated: {now_utc.isoformat().replace('+00:00','Z')}_\n")

    for cat in data.get("categories", []):
        cat_name = cat.get("name", "uncategorized")
        feeds = sorted(cat.get("feeds", []), key=lambda x: x.get("priority", 99))

        items = []
        for feed in feeds:
            parsed = fetch_feed(feed["url"])
            entries = parsed.entries[:MAX_ITEMS_PER_FEED]

            for e in entries:
                title = clean_text(getattr(e, "title", ""))
                link = clean_text(getattr(e, "link", ""))
                if not title or not link:
                    continue

                key = (link.lower(), title.lower())
                if key in seen:
                    continue
                seen.add(key)

                items.append({
                    "title": title,
                    "link": link,
                    "domain": domain(link),
                    "published": parse_datetime(e),
                })

        def sort_key(x):
            return (0 if x["published"] else 1, x["published"] or "", x["domain"])
        items = sorted(items, key=sort_key)[:MAX_ITEMS_PER_CATEGORY]

        if not items:
            continue

        pretty_cat = cat_name.replace("_", " ").title()
        sections_md.append(f"## {pretty_cat}\n")
        for it in items:
            meta = it["domain"]
            if it["published"]:
                meta += f" • {it['published'][:10]}"
            sections_md.append(f"- [{it['title']}]({it['link']}) — _{meta}_")
        sections_md.append("")

    out_path.write_text("\n".join(sections_md).strip() + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")

if __name__ == "__main__":
    build()
