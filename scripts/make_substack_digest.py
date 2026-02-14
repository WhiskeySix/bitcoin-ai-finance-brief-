import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BRIEFS_DIR = ROOT / "briefs"

PPLX_API_KEY = os.getenv("PPLX_API_KEY", "").strip()
PPLX_MODEL = os.getenv("PPLX_MODEL", "sonar")  # safe default; change later if you want

def find_today_brief():
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    path = BRIEFS_DIR / f"{date_str}.md"
    return date_str, path

def call_perplexity(prompt: str) -> str:
    if not PPLX_API_KEY:
        raise RuntimeError("Missing PPLX_API_KEY env var (GitHub Secret).")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": PPLX_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert financial/tech news editor. Be concise and accurate. Do not invent facts."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def main():
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

    date_str, src_path = find_today_brief()
    if not src_path.exists():
        raise RuntimeError(f"Expected source brief not found: {src_path}")

    raw = src_path.read_text(encoding="utf-8")

    prompt = f"""
Turn the following markdown link-dump into a Substack-ready daily digest.

Rules:
- Output MUST be valid Markdown.
- Start with a strong title line.
- Then a short opening paragraph (2–4 sentences) that frames the day across Bitcoin + AI + Finance.
- Then create THREE sections: Bitcoin, AI, Finance.
- Under each section: 3–5 bullet takeaways MAX, each takeaway should reference specific linked headlines from the input.
- Then include a "Read More" subsection with the best 5 links total (mixed across categories).
- Do NOT invent numbers, quotes, or claims not supported by the headlines.
- Keep it punchy, like a morning brief.

Here is the source brief:

{raw}
""".strip()

    digest = call_perplexity(prompt)

    out_path = BRIEFS_DIR / f"{date_str}-substack.md"
    out_path.write_text(digest.strip() + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")

if __name__ == "__main__":
    main()
