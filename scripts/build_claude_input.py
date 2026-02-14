import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter

import feedparser

ROOT = Path(__file__).resolve().parents[1]
FEEDS_PATH = ROOT / "feeds.json"
OUT_DIR = ROOT / "briefs"

DAYS_BACK = 3
TRENDING_LIMIT = 3
TECH_LIMIT = 1
HEADLINE_STRIP_LIMIT = 6

KEYWORDS = [
    "ai","bitcoin","crypto","etf","sec","china","credit",
    "stablecoin","rates","inflation","macro","fed",
    "yield","nvidia","tesla","trump","markets"
]

TECH_SOURCES = ["glassnode","huggingface","messari"]
BLOCK_WORDS = ["earnings call","transcript","sec filing"]
CHART_SOURCES = ["cnbc","bloomberg","wsj","ft.com","marketwatch"]

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

def score_title(title):
    t = title.lower()
    return sum(1 for w in KEYWORDS if w in t)

def detect_narrative(headlines):
    tokens=[]
    for h in headlines:
        for w in KEYWORDS:
            if w in h.lower():
                tokens.append(w)
    if not tokens:
        return None
    top = Counter(tokens).most_common(3)
    return ", ".join([t[0].upper() for t in top])

def build():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    feeds = load_feeds()

    date_str = datetime.now().strftime("%Y-%m-%d")
    out = OUT_DIR / f"{date_str}-CLAUDE-INPUT.md"

    sections={
        "bitcoin_crypto":{"items":[]},
        "ai":{"items":[]},
        "finance_macro":{"items":[]},
    }

    chart_candidates=[]
    all_titles=[]
    headline_pool=[]

    for cat in feeds["categories"]:
        name=cat["name"]
        if name not in sections:
            continue

        for feed in cat["feeds"]:
            parsed=fetch(feed["url"])

            for e in parsed.entries[:15]:
                title=clean_text(getattr(e,"title",""))
                link=clean_text(getattr(e,"link",""))

                if not title or not link:
                    continue

                if any(b in title.lower() for b in BLOCK_WORDS):
                    continue

                dt=parse_datetime(e)
                if not within_days(dt):
                    continue

                d=domain(link)
                score=score_title(title)

                item={
                    "title":title,
                    "link":link,
                    "score":score,
                    "tech": any(t in d for t in TECH_SOURCES),
                    "domain":d
                }

                sections[name]["items"].append(item)
                all_titles.append(title)
                headline_pool.append(item)

                if any(src in d for src in CHART_SOURCES):
                    chart_candidates.append(item)

    for key in sections:
        sections[key]["items"].sort(
            key=lambda x:(x["score"],not x["tech"]),
            reverse=True
        )

    headline_pool.sort(key=lambda x:x["score"],reverse=True)
    chart_candidates.sort(key=lambda x:x["score"],reverse=True)

    narrative = detect_narrative(all_titles)

    md=[]
    md.append("# DAILY TRENDING BRIEF — CLAUDE INPUT\n")
    md.append("Write like a sharp but normal dad tracking Bitcoin, AI, and markets.")
    md.append("Not corporate. Not nerdy essays. Explain why things matter in real life.\n")

    # 🧠 Narrative Engine
    if narrative:
        md.append("## 🧠 NARRATIVE OF THE DAY — WHY THIS STUFF IS CONNECTED\n")
        md.append(f"Main crossover themes today: {narrative}.")
        md.append("Open with a strong macro observation tying these together.\n")

    # 👀 HEADLINES STRIP
    if headline_pool:
        md.append("## 👀 YOU’LL HEAR THIS TODAY\n")
        for item in headline_pool[:HEADLINE_STRIP_LIMIT]:
            md.append(f"- [{item['title']}]({item['link']})")
        md.append("Write these as rapid-fire observations before the deep sections.\n")

    def write_section(label,key):
        md.append(f"## {label} — WHAT PEOPLE ARE ACTUALLY TALKING ABOUT\n")

        trending=[]
        tech=[]

        for item in sections[key]["items"]:
            line=f"- [{item['title']}]({item['link']})"

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

    # 📊 CHART SIGNAL
    if chart_candidates:
        md.append("## 📊 CHART SIGNAL — WHAT SMART MONEY IS WATCHING\n")
        top_chart=chart_candidates[0]
        md.append(f"- [{top_chart['title']}]({top_chart['link']})\n")
        md.append("Explain the macro signal like talking to a smart friend.\n")

    md.append("\nWrite a Substack-ready daily brief from this.")
    md.append("Tone: grounded, curious, slightly opinionated.")

    out.write_text("\n".join(md),encoding="utf-8")
    print(f"Wrote: {out}")

if __name__=="__main__":
    build()
