"""
Phase 5: Final Distribution
INDMoney App Review Insights Analyser

Reads the finalized Markdown note from Phase 3, emails it via SMTP
to the designated PM alias, and performs a hard delete on all transient
data files (Phase 1 JSON, Phase 2 JSON) to satisfy the zero-retention policy.
"""

import os
import sys
import smtplib
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "avunjain@gmail.com")

# Required transient files to delete after successful dispatch
FILES_TO_DELETE = [
    Path("../phase1/reviews_clean.json"),
    Path("../phase2/analysis_output.json")
]
NOTE_PATH = Path("../phase3/weekly_insight_note.md")


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_note() -> str:
    """Read the finalized Markdown note."""
    if not NOTE_PATH.exists():
        sys.exit(f"[Phase 5] ERROR: Note not found at {NOTE_PATH.resolve()}")
    with open(NOTE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def send_email(subject: str, body: str) -> None:
    """Send an email using Gmail's SMTP server."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        sys.exit("[Phase 5] ERROR: Missing SENDER_EMAIL or SENDER_PASSWORD in .env")

    print(f"[Phase 5] Connecting to SMTP server to email {RECEIVER_EMAIL}...")
    
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        # Standard Gmail SMTP settings
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("[Phase 5] ✅ Email dispatched successfully.")
    except Exception as e:
        sys.exit(f"[Phase 5] ❌ SMTP Error: {e}")


def cleanup_transient_files() -> None:
    """Hard delete all intermediate data to ensure zero-retention of raw reviews & JSON."""
    deleted_count = 0
    for file_path in FILES_TO_DELETE:
        if file_path.exists():
            try:
                os.remove(file_path)
                print(f"[Phase 5] 🗑️  Deleted: {file_path.name}")
                deleted_count += 1
            except Exception as e:
                print(f"[Phase 5] ⚠️ Failed to delete {file_path.name}: {e}")
                
    if deleted_count > 0:
        print("[Phase 5] ✅ Zero-retention policy enforced. Transient data cleared.")
    else:
        print("[Phase 5] No transient files needed deletion.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("  INDMoney Insights — Phase 5: Distribution & Cleanup")
    print("═" * 60)

    # 1. Read Note
    note_content = read_note()
    
    # 2. Email the Note
    subject = "🚨 Weekly INDMoney App Review Insights"
    send_email(subject, note_content)
    
    # 3. Security Cleanup
    cleanup_transient_files()
    
    print("\n[Phase 5] Done. ✓ Weekly pipeline complete!")


if __name__ == "__main__":
    main()
