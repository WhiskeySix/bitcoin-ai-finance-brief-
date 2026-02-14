import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser

ROOT = Path(__file__).resolve().parents[1]
FEEDS_PATH = ROOT / "feeds.json"
OUT_DIR = ROOT / "briefs"

DAYS_BACK = 3

BLOCK_WORDS = [
    "earnings call",
    "transcript",
    "sec filing",
    "quarterly results",
]

TECH_SOURCES = [
    "glassnode",
    "huggingface",
    "messari",
]

TRENDING_LIMIT = 3
TECH_LIMIT = 1

def clean_text(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""

def parse_datetime(entry):
    for key in ("published_parsed","updated_parsed"):
        t = getattr(entry,key,None)
        if t:
            return datetime(*t[:6],tzinfo=timezone.utc)
    return None

def within_days(dt):
    if not dt:
        return True
    return (datetime.now(timezone.utc)-dt).days <= DAYS_BACK

def load_feeds():
    with open(FEEDS_PATH,"r",encoding="utf-8") as f:
        return json.load(f)

def fetch(url):
    return feedparser.parse(url)

def build():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    feeds = load_feeds()

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    out = OUT_DIR / f"{date_str}-CLAUDE-INPUT.md"

    sections = {
        "bitcoin_crypto": {"trending":[],"tech":[]},
        "ai": {"trending":[],"tech":[]},
        "finance_macro": {"trending":[],"tech":[]}
    }

    for cat in feeds["categories"]:
        name = cat["name"]
        if name not in sections:
            continue

        for feed in cat["feeds"]:
            parsed = fetch(feed["url"])

            for e in parsed.entries[:10]:
                title = clean_text(getattr(e,"title",""))
                link = clean_text(getattr(e,"link",""))

                if not title or not link:
                    continue

                if any(b in title.lower() for b in BLOCK_WORDS):
                    continue

                dt = parse_datetime(e)
                if not within_days(dt):
                    continue

                d = domain(link)
                item = f"- [{title}]({link})"

                if any(t in d for t in TECH_SOURCES):
                    if len(sections[name]["tech"]) < TECH_LIMIT:
                        sections[name]["tech"].append(item)
                else:
                    if len(sections[name]["trending"]) < TRENDING_LIMIT:
                        sections[name]["trending"].append(item)

    md = []

    # 🔥 OPUS VOICE PRIMER
    md.append("# DAILY TRENDING BRIEF — CLAUDE INPUT\n")
    md.append("You are writing like a sharp but normal dad who follows Bitcoin, AI, and markets daily.")
    md.append("Not corporate. Not nerdy. No hype bro language either.")
    md.append("Explain why things matter in real life — money, tech shifts, momentum.\n")

    md.append("FORMAT YOU MUST FOLLOW:")
    md.append("- Strong opening summary")
    md.append("- Clear sections")
    md.append("- Short punchy insights")
    md.append("- Sound human, not like a research report\n")

    def write_section(label,key):
        md.append(f"## {label} — WHAT PEOPLE ARE ACTUALLY TALKING ABOUT\n")
        md.extend(sections[key]["trending"])
        md.append("")
        md.append("### TECHNICAL PICK (Explain simply — assume reader is smart but busy)")
        md.extend(sections[key]["tech"])
        md.append("")

    write_section("🟠 BITCOIN","bitcoin_crypto")
    write_section("🤖 AI","ai")
    write_section("💰 FINANCE","finance_macro")

    md.append("\nWrite a Substack-ready daily brief using the above structure.")
    md.append("Tone: grounded, curious, a little opinionated, never robotic.")

    out.write_text("\n".join(md),encoding="utf-8")
    print(f"Wrote: {out}")

if __name__=="__main__":
    build()
