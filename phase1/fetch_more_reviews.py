"""
Fetch 500 more *distinct* reviews by cycling through all star ratings (1–5)
to avoid duplicates from the same "newest" pool. Merges into reviews_clean.json.
"""

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from google_play_scraper import Sort, reviews

APP_ID = "in.indwealth"
ROLLING_WEEKS = 6
MIN_WORDS = 5
OUTPUT_FILE = "reviews_clean.json"

CURSE_WORDS = {
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty", "asshole", "ass",
    "bitch", "bitches", "damn", "crap",
    "bastard", "dick", "piss", "cunt",
    "twat", "wank", "wanker", "bullshit",
}

PII_PATTERNS = [
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]{1}\b"), "[PAN_REDACTED]"),
    (re.compile(r"\b[6-9]\d{9}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),
    (re.compile(r"\b\d{10}\b"), "[PHONE_REDACTED]"),
]

def strip_emojis(text):
    cleaned = []
    for char in text:
        cat = unicodedata.category(char)
        cp = ord(char)
        if cat in ("So", "Sm", "Sk", "Cs"):
            continue
        if (
            0x1F600 <= cp <= 0x1F64F or 0x1F300 <= cp <= 0x1F5FF
            or 0x1F680 <= cp <= 0x1F6FF or 0x1F700 <= cp <= 0x1F77F
            or 0x1F780 <= cp <= 0x1F7FF or 0x1F800 <= cp <= 0x1F8FF
            or 0x1F900 <= cp <= 0x1F9FF or 0x1FA00 <= cp <= 0x1FA6F
            or 0x1FA70 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x26FF
            or 0x2700 <= cp <= 0x27BF   or 0xFE00 <= cp <= 0xFE0F
            or cp == 0x200D or cp == 0xFE0F
        ):
            continue
        cleaned.append(char)
    return "".join(cleaned).strip()

def redact_pii(text):
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

def is_english(text):
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    ascii_alpha = [c for c in alpha_chars if ord(c) < 128]
    return (len(ascii_alpha) / len(alpha_chars)) >= 0.80

def contains_curse_words(text):
    return bool(set(re.findall(r"\b\w+\b", text.lower())) & CURSE_WORDS)

def word_count(text):
    return len(text.split())

def is_within_window(date, weeks):
    cutoff = datetime.now(tz=timezone.utc) - timedelta(weeks=weeks)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date >= cutoff

def main():
    # Load existing
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        existing = json.load(f)
    existing_reviews = existing["reviews"]
    existing_stats   = existing["metadata"]["stats"]
    seen_texts       = {r["text"] for r in existing_reviews}
    print(f"Loaded {len(existing_reviews)} existing clean reviews.")

    # Fetch 100 reviews per star rating (1★–5★) = 500 raw total
    raw_all = []
    for star in range(1, 6):
        print(f"  Fetching 100 reviews with {star}★ rating...")
        batch, _ = reviews(
            APP_ID,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=100,
            filter_score_with=star,
        )
        raw_all.extend(batch)
    print(f"Fetched {len(raw_all)} raw reviews across all star ratings.\n")

    new_clean = []
    stats = {"total": len(raw_all), "dropped_time": 0, "dropped_lang": 0,
             "dropped_short": 0, "dropped_curse": 0, "dropped_dupe": 0, "kept": 0}

    for r in raw_all:
        review_date = r.get("at", datetime.min)
        if not is_within_window(review_date, ROLLING_WEEKS):
            stats["dropped_time"] += 1
            continue

        content = strip_emojis(r.get("content", ""))

        if not is_english(content):
            stats["dropped_lang"] += 1
            continue

        if word_count(content) <= MIN_WORDS:
            stats["dropped_short"] += 1
            continue

        if contains_curse_words(content):
            stats["dropped_curse"] += 1
            continue

        content = redact_pii(content)

        if content in seen_texts:
            stats["dropped_dupe"] += 1
            continue

        new_clean.append({
            "rating": r.get("score"),
            "text": content,
            "date": review_date.strftime("%Y-%m-%d"),
        })
        seen_texts.add(content)
        stats["kept"] += 1

    print("[Batch — By Star Rating] Filtering Summary:")
    for k, v in stats.items():
        print(f"  {k:<22}: {v}")

    merged = existing_reviews + new_clean

    # Accumulate cumulative stats
    for key in ("total", "dropped_time", "dropped_lang", "dropped_short",
                "dropped_curse", "dropped_dupe", "kept"):
        existing_stats[key] = existing_stats.get(key, 0) + stats.get(key, 0)

    payload = {
        "metadata": {
            "app_id": APP_ID,
            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rolling_window_weeks": ROLLING_WEEKS,
            "filters_applied": [
                "english_only", "min_words_gt_5", "emoji_stripped",
                "curse_words_excluded", "pii_redacted", "deduplicated",
            ],
            "stats": existing_stats,
        },
        "reviews": merged,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nTotal clean reviews now → {len(merged)} saved to {OUTPUT_FILE}")
    print("Done. ✓")

if __name__ == "__main__":
    main()
