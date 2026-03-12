"""
Phase 2: AI-Powered Thematic Analysis
INDMoney App Review Insights Analyser

Reads sanitized reviews from phase1/reviews_clean.json, sends them to
Groq (Llama 4 Scout) for thematic grouping and insight extraction, then
saves structured results to analysis_output.json.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    sys.exit("[Phase 2] ERROR: GROQ_API_KEY not found in .env file.")

# Latest Groq model — Llama 4 Scout (17B, best for summarization & reasoning)
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

REVIEWS_PATH = Path("../phase1/reviews_clean.json")
OUTPUT_FILE   = "analysis_output.json"

# The 5 allowed themes
THEMES = [
    "Onboarding",
    "KYC",
    "Payments",
    "App Performance",
    "Customer Support",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_reviews(path: Path) -> list[dict]:
    """Load sanitized reviews from phase 1 output."""
    if not path.exists():
        sys.exit(f"[Phase 2] ERROR: reviews file not found at {path.resolve()}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    reviews = data.get("reviews", [])
    print(f"[Phase 2] Loaded {len(reviews)} clean reviews from phase 1.")
    return reviews


def build_review_block(reviews: list[dict]) -> str:
    """Concatenate reviews into a numbered list for the LLM prompt."""
    lines = []
    for i, r in enumerate(reviews, 1):
        lines.append(f'{i}. [Rating: {r["rating"]}★] [{r["date"]}] {r["text"]}')
    return "\n".join(lines)


def build_system_prompt() -> str:
    return f"""You are a Senior Product Manager at INDMoney analysing Google Play Store reviews.
Your job is to extract actionable product insights from user reviews — strictly following these rules:

RULES:
1. Categorize ALL reviews into EXACTLY these 5 themes: {", ".join(THEMES)}.
2. Identify the TOP 3 most discussed themes (by volume and sentiment intensity).
3. Extract exactly 3 representative user quotes (verbatim from the reviews, no edits).
   - Quotes must NOT contain usernames, emails or any IDs.
   - Prefer quotes that are specific, emotive, and actionable.
4. Generate exactly 3 concrete, actionable product improvement ideas grounded in the feedback.
5. Output ONLY valid JSON. No markdown. No explanation outside the JSON.

OUTPUT FORMAT (strict JSON schema):
{{
  "theme_distribution": {{
    "Onboarding": <integer count>,
    "KYC": <integer count>,
    "Payments": <integer count>,
    "App Performance": <integer count>,
    "Customer Support": <integer count>
  }},
  "top_3_themes": [
    {{
      "theme": "<theme name>",
      "count": <integer>,
      "sentiment": "<Positive | Negative | Mixed>",
      "summary": "<1-2 sentence summary of what users are saying>"
    }}
  ],
  "user_quotes": [
    {{
      "quote": "<verbatim review text>",
      "rating": <integer 1-5>,
      "theme": "<theme name>"
    }}
  ],
  "action_ideas": [
    {{
      "idea": "<specific, actionable product improvement>",
      "theme": "<related theme>",
      "impact": "<High | Medium | Low>"
    }}
  ]
}}"""


def build_user_prompt(review_block: str) -> str:
    return f"""Here are the INDMoney app reviews to analyse:

{review_block}

Classify every review into one of the 5 themes, then return the JSON output as specified."""


def call_groq(client: Groq, system_prompt: str, user_prompt: str) -> str:
    """Call Groq API and return the raw response text."""
    print(f"[Phase 2] Calling Groq ({MODEL})...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,      # Low temp for consistent, structured output
        max_tokens=2048,
        response_format={"type": "json_object"},  # Enforce JSON mode
    )
    raw = response.choices[0].message.content
    print(f"[Phase 2] Groq responded. Tokens used — "
          f"prompt: {response.usage.prompt_tokens}, "
          f"completion: {response.usage.completion_tokens}, "
          f"total: {response.usage.total_tokens}")
    return raw


def parse_and_validate(raw: str) -> dict:
    """Parse JSON response and do basic schema validation."""
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"[Phase 2] ERROR: Groq returned invalid JSON.\n{e}\nRaw: {raw[:500]}")

    required_keys = {"theme_distribution", "top_3_themes", "user_quotes", "action_ideas"}
    missing = required_keys - result.keys()
    if missing:
        sys.exit(f"[Phase 2] ERROR: Missing keys in response: {missing}")

    if len(result["top_3_themes"]) != 3:
        print(f"[Phase 2] WARNING: Expected 3 top themes, got {len(result['top_3_themes'])}")
    if len(result["user_quotes"]) != 3:
        print(f"[Phase 2] WARNING: Expected 3 quotes, got {len(result['user_quotes'])}")
    if len(result["action_ideas"]) != 3:
        print(f"[Phase 2] WARNING: Expected 3 action ideas, got {len(result['action_ideas'])}")

    return result


def save_output(analysis: dict, reviews_count: int) -> None:
    """Wrap analysis with metadata and save to JSON."""
    from datetime import datetime, timezone
    payload = {
        "metadata": {
            "model": MODEL,
            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reviews_analysed": reviews_count,
            "themes_available": THEMES,
        },
        "analysis": analysis,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[Phase 2] Analysis saved → {OUTPUT_FILE}")


def print_summary(analysis: dict) -> None:
    """Print a readable summary to the console."""
    print("\n" + "═" * 60)
    print("  INDMoney Weekly Review Insights — Phase 2 Summary")
    print("═" * 60)

    print("\n📊 Theme Distribution:")
    for theme, count in analysis["theme_distribution"].items():
        bar = "█" * count
        print(f"  {theme:<20} {count:>3}  {bar}")

    print("\n🏆 Top 3 Themes:")
    for i, t in enumerate(analysis["top_3_themes"], 1):
        print(f"  {i}. {t['theme']} ({t['count']} reviews, {t['sentiment']})")
        print(f"     → {t['summary']}")

    print("\n💬 Representative User Quotes:")
    for i, q in enumerate(analysis["user_quotes"], 1):
        print(f'  {i}. [{q["rating"]}★ | {q["theme"]}] "{q["quote"][:120]}..."')

    print("\n💡 Action Ideas:")
    for i, a in enumerate(analysis["action_ideas"], 1):
        print(f"  {i}. [{a['impact']} Impact | {a['theme']}] {a['idea']}")

    print("\n" + "═" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = Groq(api_key=GROQ_API_KEY)

    # Load data from phase 1
    reviews = load_reviews(REVIEWS_PATH)

    # Build prompts
    review_block  = build_review_block(reviews)
    system_prompt = build_system_prompt()
    user_prompt   = build_user_prompt(review_block)

    # Call Groq
    raw_response = call_groq(client, system_prompt, user_prompt)

    # Parse & validate
    analysis = parse_and_validate(raw_response)

    # Save output
    save_output(analysis, len(reviews))

    # Print summary
    print_summary(analysis)

    print("\n[Phase 2] Done. ✓")


if __name__ == "__main__":
    main()
