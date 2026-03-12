"""
Phase 6: Orchestration Script (main.py)
INDMoney App Review Insights Analyser

Master script that runs the full pipeline:
  Phase 1 -> Phase 2 -> Phase 3 -> Phase 5
Designed to be invoked by the GitHub Action scheduler every Thursday at 3PM IST.
"""

import os
import sys
import json
import re
import unicodedata
import smtplib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

# ─── Load env from .env if running locally ────────────────────────────────────
try:
    from dotenv import load_dotenv
    # Look for a root-level .env first
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass  # In GitHub Actions, secrets come in as actual env vars

# ─────────────────────────────── CONFIG ──────────────────────────────────────

APP_ID            = "in.indwealth"
REVIEW_COUNT      = int(os.getenv("REVIEW_COUNT", 1000))  # Env-configurable, defaults to 1000
ROLLING_WEEKS     = 6
MIN_WORDS         = 5
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
SENDER_EMAIL      = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD   = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL    = os.getenv("RECEIVER_EMAIL", "akshat.lallan678@gmail.com")

GROQ_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"
GEMINI_MODEL = "gemini-2.5-flash"

REVIEWS_FILE       = Path("../phase1/reviews_clean.json")
ANALYSIS_FILE      = Path("../phase2/analysis_output.json")
NOTE_FILE          = Path("../phase3/weekly_insight_note.md")

THEMES = ["Onboarding", "KYC", "Payments", "App Performance", "Customer Support"]

CURSE_WORDS = {
    "fuck", "fucking", "fucked", "fucker", "shit", "shitty",
    "asshole", "ass", "bitch", "bitches", "damn", "crap",
    "bastard", "dick", "piss", "cunt", "twat", "wank", "wanker", "bullshit",
}

PII_PATTERNS = [
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]{1}\b"), "[PAN_REDACTED]"),
    (re.compile(r"\b[6-9]\d{9}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),
    (re.compile(r"\b\d{10}\b"), "[PHONE_REDACTED]"),
]

# ─── Phase 1 Helpers ──────────────────────────────────────────────────────────

def strip_emojis(text):
    cleaned = []
    for char in text:
        cat = unicodedata.category(char)
        cp = ord(char)
        if cat in ("So", "Sm", "Sk", "Cs"):
            continue
        if (0x1F600 <= cp <= 0x1F64F or 0x1F300 <= cp <= 0x1F5FF
                or 0x1F680 <= cp <= 0x1F6FF or 0x1F900 <= cp <= 0x1F9FF
                or 0x2600 <= cp <= 0x26FF   or 0x2700 <= cp <= 0x27BF
                or 0xFE00 <= cp <= 0xFE0F   or cp == 0x200D):
            continue
        cleaned.append(char)
    return "".join(cleaned).strip()

def redact_pii(text):
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

def is_english(text):
    alphas = [c for c in text if c.isalpha()]
    if not alphas:
        return False
    return len([c for c in alphas if ord(c) < 128]) / len(alphas) >= 0.80

def has_curse(text):
    return bool(set(re.findall(r"\b\w+\b", text.lower())) & CURSE_WORDS)

def in_window(date, weeks):
    cutoff = datetime.now(tz=timezone.utc) - timedelta(weeks=weeks)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date >= cutoff

# ─── Phase 1: Fetch & Sanitize ───────────────────────────────────────────────

def run_phase1():
    print("\n" + "=" * 60)
    print("  PHASE 1: Data Acquisition & Preprocessing")
    print("=" * 60)
    try:
        from google_play_scraper import Sort, reviews as gp_reviews
    except ImportError:
        sys.exit("[Phase 1] ERROR: google-play-scraper not installed.")

    # Fetch across all star ratings to maximise diversity (200 per star = 1000)
    per_star = REVIEW_COUNT // 5
    raw_all = []
    for star in range(1, 6):
        print(f"  Fetching {per_star} reviews with {star}★ rating...")
        batch, _ = gp_reviews(
            APP_ID, lang="en", country="in",
            sort=Sort.NEWEST, count=per_star, filter_score_with=star,
        )
        raw_all.extend(batch)
    print(f"[Phase 1] Fetched {len(raw_all)} raw reviews.")

    clean, stats = [], {
        "total": len(raw_all), "dropped_time": 0, "dropped_lang": 0,
        "dropped_short": 0, "dropped_curse": 0, "kept": 0,
    }
    seen = set()
    for r in raw_all:
        review_date = r.get("at", datetime.min)
        if not in_window(review_date, ROLLING_WEEKS):
            stats["dropped_time"] += 1; continue
        content = strip_emojis(r.get("content", ""))
        if not is_english(content):
            stats["dropped_lang"] += 1; continue
        if len(content.split()) <= MIN_WORDS:
            stats["dropped_short"] += 1; continue
        if has_curse(content):
            stats["dropped_curse"] += 1; continue
        content = redact_pii(content)
        if content in seen:
            continue
        seen.add(content)
        clean.append({"rating": r.get("score"), "text": content,
                      "date": review_date.strftime("%Y-%m-%d")})
        stats["kept"] += 1

    REVIEWS_FILE.parent.mkdir(exist_ok=True)
    payload = {
        "metadata": {"app_id": APP_ID, "stats": stats,
                     "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "reviews": clean,
    }
    REVIEWS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Phase 1] {stats['kept']} clean reviews saved → {REVIEWS_FILE}")

# ─── Phase 2: Groq Analysis ───────────────────────────────────────────────────

def run_phase2():
    print("\n" + "=" * 60)
    print("  PHASE 2: AI-Powered Thematic Analysis (Groq)")
    print("=" * 60)
    if not GROQ_API_KEY:
        sys.exit("[Phase 2] ERROR: GROQ_API_KEY not set.")
    try:
        from groq import Groq
    except ImportError:
        sys.exit("[Phase 2] ERROR: groq not installed.")

    data = json.loads(REVIEWS_FILE.read_text(encoding="utf-8"))
    reviews = data["reviews"]
    print(f"[Phase 2] Loaded {len(reviews)} reviews.")

    lines = [f'{i+1}. [Rating: {r["rating"]}★] [{r["date"]}] {r["text"]}'
             for i, r in enumerate(reviews)]
    review_block = "\n".join(lines)

    system = f"""You are a Senior PM at INDMoney. Categorize ALL reviews into these 5 themes: {", ".join(THEMES)}.
Return ONLY valid JSON with this exact schema:
{{
  "theme_distribution": {{"Onboarding": 0, "KYC": 0, "Payments": 0, "App Performance": 0, "Customer Support": 0}},
  "top_3_themes": [{{"theme": "", "count": 0, "sentiment": "", "summary": ""}}],
  "user_quotes": [{{"quote": "", "rating": 0, "theme": ""}}],
  "action_ideas": [{{"idea": "", "theme": "", "impact": ""}}]
}}
top_3_themes must have exactly 3 items. user_quotes must have exactly 3 items. action_ideas must have exactly 3 items. No PII in quotes."""

    client = Groq(api_key=GROQ_API_KEY)
    print(f"[Phase 2] Calling Groq ({GROQ_MODEL})...")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Analyse these reviews:\n\n{review_block}"},
        ],
        temperature=0.2,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    analysis = json.loads(raw)

    ANALYSIS_FILE.parent.mkdir(exist_ok=True)
    payload = {
        "metadata": {"model": GROQ_MODEL, "reviews_analysed": len(reviews),
                     "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "analysis": analysis,
    }
    ANALYSIS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Phase 2] Analysis saved → {ANALYSIS_FILE}")

# ─── Phase 3: Gemini Note Generation ─────────────────────────────────────────

def run_phase3():
    print("\n" + "=" * 60)
    print("  PHASE 3: Note Generation (Gemini)")
    print("=" * 60)
    if not GEMINI_API_KEY:
        sys.exit("[Phase 3] ERROR: GEMINI_API_KEY not set.")
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit("[Phase 3] ERROR: google-genai not installed.")

    data = json.loads(ANALYSIS_FILE.read_text(encoding="utf-8"))
    analysis = data["analysis"]

    system_instruction = """You are a Senior Product Manager at INDMoney.
Draft a scannable, creative one-page weekly note from the insights data.

## CRITICAL FORMATTING RULES FOR EMAIL DELIVERY:
1. MAX 250 WORDS. No PII. Professional yet engaging tone.
2. NEVER use '#' symbols for headings.
3. NEVER use '*' symbols for bullet points. Use standard dashes '-' instead.
4. Make headings visually distinct by using **BOLD ALL CAPS**.
5. SUBHEADINGS within themes must be **Bold Title Case**.
6. REQUIRED: You MUST insert exactly TWO empty newlines between every section so there is clear, wide spacing.

REQUIRED STRUCTURE:

**WEEKLY INDMONEY APP REVIEW INSIGHTS** 🚨

[Insert exactly two empty lines here]

**TOP 3 THEMES**
- **[Theme Name]**: [Punchy sentence explaining the sentiment/focus]
- **[Theme Name]**: [Punchy sentence explaining the sentiment/focus]
- **[Theme Name]**: [Punchy sentence explaining the sentiment/focus]

[Insert exactly two empty lines here]

**VOICE OF CUSTOMER**
"Quote 1"
"Quote 2"
"Quote 3"

[Insert exactly two empty lines here]

**ACTION ITEMS**
1. **[Action Item]**: [Explanation]. Impact: **[High/Medium/Low]**
2. **[Action Item]**: [Explanation]. Impact: **[High/Medium/Low]**
3. **[Action Item]**: [Explanation]. Impact: **[High/Medium/Low]**
"""

    user_prompt = f"Generate the weekly insights note from this data:\n\n```json\n{json.dumps(analysis, indent=2)}\n```"

    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"[Phase 3] Calling Gemini ({GEMINI_MODEL})...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7),
    )
    note = response.text
    NOTE_FILE.parent.mkdir(exist_ok=True)
    NOTE_FILE.write_text(note, encoding="utf-8")
    wc = len(note.split())
    print(f"[Phase 3] Note saved ({wc} words) → {NOTE_FILE}")

# ─── Phase 5: Email & Cleanup ─────────────────────────────────────────────────

def run_phase5():
    print("\n" + "=" * 60)
    print("  PHASE 5: Email Dispatch & Cleanup")
    print("=" * 60)
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        sys.exit("[Phase 5] ERROR: SENDER_EMAIL / SENDER_PASSWORD not set.")

    note_body = NOTE_FILE.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = "🚨 Weekly INDMoney App Review Insights"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL
    msg.set_content(note_body)

    print(f"[Phase 5] Sending email to {RECEIVER_EMAIL}...")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("[Phase 5] Email dispatched successfully.")
    except Exception as e:
        sys.exit(f"[Phase 5] SMTP Error: {e}")

    # Security cleanup
    for f in [REVIEWS_FILE, ANALYSIS_FILE]:
        if f.exists():
            f.unlink()
            print(f"[Phase 5] Deleted: {f}")
    print("[Phase 5] Zero-retention policy enforced.")

# ─── Orchestrator ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 60)
    print("  INDMoney Review Insights — Weekly Pipeline")
    print(f"  Run time: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("█" * 60)

    run_phase1()
    run_phase2()
    run_phase3()
    run_phase5()

    print("\n" + "█" * 60)
    print("  Pipeline complete! Weekly insights dispatched.")
    print("█" * 60)


if __name__ == "__main__":
    main()
