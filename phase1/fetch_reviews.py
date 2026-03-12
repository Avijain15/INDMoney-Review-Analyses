"""
Phase 1: Data Acquisition & Preprocessing
INDMoney App Review Insights Analyser

Fetches 500 public reviews from Google Play Store for in.indwealth,
applies strict filtering (language, length, emoji, curse words), strips
all PII, and saves the sanitized output to reviews_clean.json.
"""

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from google_play_scraper import Sort, reviews


# ─────────────────────────────── CONFIG ──────────────────────────────────────

APP_ID = "in.indwealth"
REVIEW_COUNT = 500           # Total reviews to fetch (before filtering)
ROLLING_WEEKS = 6            # Keep only reviews from the last N weeks
MIN_WORDS = 5                # Exclude reviews with word count <= this value
OUTPUT_FILE = "reviews_clean.json"

# Profanity / curse word blocklist (extend as needed)
CURSE_WORDS = {
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty",
    "asshole", "ass",
    "bitch", "bitches",
    "damn", "crap",
    "bastard", "dick", "piss",
    "cunt", "twat", "wank", "wanker",
    "bullshit",
}

# PII redaction patterns
PII_PATTERNS = [
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]{1}\b"), "[PAN_REDACTED]"),           # PAN card
    (re.compile(r"\b[6-9]\d{9}\b"), "[PHONE_REDACTED]"),                     # Indian mobile numbers
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),  # Emails
    (re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),                        # Aadhaar (12 digits)
    (re.compile(r"\b\d{10}\b"), "[PHONE_REDACTED]"),                          # Generic 10-digit numbers
]


# ─────────────────────────────── HELPERS ─────────────────────────────────────

def strip_emojis(text: str) -> str:
    """Remove emoji and other non-text unicode characters from a string."""
    cleaned = []
    for char in text:
        cat = unicodedata.category(char)
        cp = ord(char)
        # Drop Modifier_Symbol, Other_Symbol, Surrogate, and emoji ranges
        if cat in ("So", "Sm", "Sk", "Cs"):
            continue
        # Drop characters in common emoji unicode blocks
        if (
            0x1F600 <= cp <= 0x1F64F  # Emoticons
            or 0x1F300 <= cp <= 0x1F5FF  # Misc symbols & pictographs
            or 0x1F680 <= cp <= 0x1F6FF  # Transport & map
            or 0x1F700 <= cp <= 0x1F77F  # Alchemical symbols
            or 0x1F780 <= cp <= 0x1F7FF  # Geometric shapes extended
            or 0x1F800 <= cp <= 0x1F8FF  # Supplemental arrows-C
            or 0x1F900 <= cp <= 0x1F9FF  # Supplemental symbols & pictographs
            or 0x1FA00 <= cp <= 0x1FA6F  # Chess symbols
            or 0x1FA70 <= cp <= 0x1FAFF  # Symbols & pictographs extended-A
            or 0x2600 <= cp <= 0x26FF    # Misc symbols
            or 0x2700 <= cp <= 0x27BF    # Dingbats
            or 0xFE00 <= cp <= 0xFE0F    # Variation selectors
            or 0x200D == cp              # Zero-width joiner
            or 0xFE0F == cp              # Variation selector-16
        ):
            continue
        cleaned.append(char)
    return "".join(cleaned).strip()


def redact_pii(text: str) -> str:
    """Apply regex-based PII redaction patterns to text."""
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_english(text: str) -> bool:
    """
    Heuristic English language check:
    Checks that the ratio of ASCII alphabetic characters to total
    alphabetic characters is above 80%, which reliably excludes
    Devanagari, Arabic, Chinese, etc.
    """
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    ascii_alpha = [c for c in alpha_chars if ord(c) < 128]
    return (len(ascii_alpha) / len(alpha_chars)) >= 0.80


def contains_curse_words(text: str) -> bool:
    """Return True if the text contains any word from the blocklist."""
    words = re.findall(r"\b\w+\b", text.lower())
    return bool(set(words) & CURSE_WORDS)


def word_count(text: str) -> int:
    """Return the number of words in a string."""
    return len(text.split())


def is_within_window(date: datetime, weeks: int) -> bool:
    """Return True if date falls within the rolling N-week window."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(weeks=weeks)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date >= cutoff


# ─────────────────────────────── CORE ────────────────────────────────────────

def fetch_raw_reviews(app_id: str, count: int) -> list[dict]:
    """Fetch raw reviews from Google Play Store."""
    print(f"[Phase 1] Fetching {count} reviews for '{app_id}'...")
    result, _ = reviews(
        app_id,
        lang="en",
        country="in",
        sort=Sort.NEWEST,
        count=count,
    )
    print(f"[Phase 1] Fetched {len(result)} raw reviews.")
    return result


def sanitize_reviews(raw: list[dict]) -> list[dict]:
    """
    Apply all filtering and anonymization steps:
      1. Time window filter (last 6 weeks)
      2. English-only filter
      3. Minimum word length filter (> 5 words)
      4. Emoji stripping
      5. Curse word filter
      6. PII redaction
      7. Drop PII fields (title, userName, userImage, reviewId, etc.)
    """
    cutoff_date = datetime.now(tz=timezone.utc) - timedelta(weeks=ROLLING_WEEKS)
    clean = []
    stats = {
        "total": len(raw),
        "dropped_time": 0,
        "dropped_lang": 0,
        "dropped_short": 0,
        "dropped_curse": 0,
        "kept": 0,
    }

    for r in raw:
        # ── 1. Time window ────────────────────────────────────────────────
        review_date: datetime = r.get("at", datetime.min)
        if not is_within_window(review_date, ROLLING_WEEKS):
            stats["dropped_time"] += 1
            continue

        # ── 2. Strip emojis first (needed before word/language checks) ────
        content: str = strip_emojis(r.get("content", ""))

        # ── 3. English-language filter ────────────────────────────────────
        if not is_english(content):
            stats["dropped_lang"] += 1
            continue

        # ── 4. Minimum word count (> 5 words) ─────────────────────────────
        if word_count(content) <= MIN_WORDS:
            stats["dropped_short"] += 1
            continue

        # ── 5. Curse word filter ──────────────────────────────────────────
        if contains_curse_words(content):
            stats["dropped_curse"] += 1
            continue

        # ── 6. PII redaction on the cleaned text ──────────────────────────
        content = redact_pii(content)

        # ── 7. Build anonymized record (no PII fields) ────────────────────
        clean.append({
            "rating": r.get("score"),
            "text": content,
            "date": review_date.strftime("%Y-%m-%d"),
        })
        stats["kept"] += 1

    print("\n[Phase 1] Filtering Summary:")
    print(f"  Total fetched      : {stats['total']}")
    print(f"  Dropped (time)     : {stats['dropped_time']}")
    print(f"  Dropped (language) : {stats['dropped_lang']}")
    print(f"  Dropped (too short): {stats['dropped_short']}")
    print(f"  Dropped (profanity): {stats['dropped_curse']}")
    print(f"  ─────────────────────────────")
    print(f"  Kept (clean)       : {stats['kept']}")

    return clean, stats


def save_output(data: list[dict], stats: dict, output_path: str) -> None:
    """Persist the sanitized reviews and run stats to a JSON file."""
    payload = {
        "metadata": {
            "app_id": APP_ID,
            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rolling_window_weeks": ROLLING_WEEKS,
            "filters_applied": [
                "english_only",
                "min_words_gt_5",
                "emoji_stripped",
                "curse_words_excluded",
                "pii_redacted",
            ],
            "stats": stats,
        },
        "reviews": data,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n[Phase 1] Saved {len(data)} clean reviews → {output_path}")


# ─────────────────────────────── MAIN ────────────────────────────────────────

def main():
    raw_reviews = fetch_raw_reviews(APP_ID, REVIEW_COUNT)
    clean_reviews, stats = sanitize_reviews(raw_reviews)
    save_output(clean_reviews, stats, OUTPUT_FILE)
    print("\n[Phase 1] Done. ✓")


if __name__ == "__main__":
    main()
