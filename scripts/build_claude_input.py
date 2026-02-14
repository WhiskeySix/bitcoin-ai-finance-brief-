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

TRENDING_LIMIT = 3
TECH_LIMIT = 1

# 🔥 CROSSOVER KEYWORDS (viral signals)
CROSSOVER_WORDS = [
    "ai","bitcoin","crypto","etf","sec","china","trump",
    "credit","stablecoin","prediction","market","nvidia",
]

TECH_SOURCES = ["glassnode","huggingface","messari"]

BLOCK_WORDS = ["earnings call","transcript","sec filing"]

def clean_text(s):
    return re.sub(r"\s+"," ",(s or "").strip())

def domain(url):
    try:
        return urlparse(url).netloc.replace("www.","")
    except:
        return ""

def parse_datetime(entry):
    for k in ("published_parsed","updated_parsed"):
        t = getattr(entry,k,None)
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

# 🔥 VIRAL SCORING
def viral_score(title):
    t = title.lower()
    score = 0
    for word in CROSSOVER_WORDS:
        if word in t:
            score += 1
    return score

def build():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    feeds = load_feeds()

    date_str = datetime.now().strftime("%Y-%m-%d")
    out = OUT_DIR / f"{date_str}-CLAUDE-INPUT.md"

    sections = {
        "bitcoin_crypto":{"items":[]},
        "ai":{"items":[]},
        "finance_macro":{"items":[]},
    }

    for cat in feeds["categories"]:
        name = cat["name"]
        if name not in sections:
            continue

        for feed in cat["feeds"]:
            parsed = fetch(feed["url"])

            for e in parsed.entries[:15]:
                title = clean_text(getattr(e,"title",""))
                link = clean_text(getattr(e,"link",""))

                if not title or not link:
                    continue

                if any(b in title.lower() for b in BLOCK_WORDS):
                    continue

                dt = parse_datetime(e)
                if not within_days(dt):
                    continue

                score = viral_score(title)
                d = domain(link)

                sections[name]["items"].append({
                    "title":title,
                    "link":link,
                    "score":score,
                    "tech": any(t in d for t in TECH_SOURCES)
                })

    # 🔥 SORT BY VIRAL SCORE
    for key in sections:
        sections[key]["items"].sort(
            key=lambda x:(x["score"],not x["tech"]),
            reverse=True
        )

    md = []

    md.append("# DAILY TRENDING BRIEF — CLAUDE INPUT\n")
    md.append("Write like a sharp but normal dad tracking Bitcoin, AI, and markets.")
    md.append("Not corporate. Not nerdy essays. Explain why it matters in real life.\n")

    def write_section(label,key):
        md.append(f"## {label} — WHAT PEOPLE ARE ACTUALLY TALKING ABOUT\n")

        trending = []
        tech = []

        for item in sections[key]["items"]:
            line = f"- [{item['title']}]({item['link']})"
            if item["tech"] and len(tech)<TECH_LIMIT:
                tech.append(line)
            elif len(trending)<TRENDING_LIMIT:
                trending.append(line)

        if not tech and trending:
            tech.append(trending[-1])

        md.extend(trending)
        md.append("")
        md.append("### TECHNICAL PICK (Explain simply — smart but busy reader)")
        md.extend(tech)
        md.append("")

    write_section("🟠 BITCOIN","bitcoin_crypto")
    write_section("🤖 AI","ai")
    write_section("💰 FINANCE","finance_macro")

    md.append("\nWrite a Substack-ready daily brief from this.")
    md.append("Tone: grounded, curious, slightly opinionated.")

    out.write_text("\n".join(md),encoding="utf-8")
    print(f"Wrote: {out}")

if __name__=="__main__":
    build()
