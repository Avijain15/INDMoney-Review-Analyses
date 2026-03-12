"""
Phase 3: Note Generation & Formatting
INDMoney App Review Insights Analyser

Reads the structured JSON insights from phase 2 (analysis_output.json),
sends them to Google Gemini for creative summarization, and outputs a 
finalized scannable one-page note (<= 250 words).
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from google import genai
from google.genai import types

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    sys.exit("[Phase 3] ERROR: GEMINI_API_KEY not found in .env file.")

MODEL = "gemini-2.5-flash"  # Fast and creative response model

ANALYSIS_PATH = Path("../phase2/analysis_output.json")
OUTPUT_FILE   = "weekly_insight_note.md"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_analysis(path: Path) -> dict:
    """Load the JSON output from phase 2."""
    if not path.exists():
        sys.exit(f"[Phase 3] ERROR: analysis file not found at {path.resolve()}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"[Phase 3] Loaded analysis output from phase 2.")
    return data["analysis"]


def build_system_instruction() -> str:
    return """You are an expert Senior Product Manager at INDMoney.
Your task is to take raw, structured analytical data about app reviews and craft it into a highly scannable, engaging, and creative one-page weekly note.

CRITICAL RULES:
1. MAX 250 WORDS. Be concise and punchy.
2. NO PII. Do not hallucinate or include any user names, emails, or IDs.
3. Keep the tone professional, objective, yet creatively engaging.
4. Output strictly in Markdown format.

REQUIRED STRUCTURE:
- Headline: "Weekly INDMoney App Review Insights" (add a relevant emoji)
- Top 3 Themes: A bulleted list of the top 3 themes with a short, punchy sentence explaining the sentiment/focus.
- Voice of Customer: Present the 3 user quotes cleanly and beautifully.
- Action Items: Present the 3 action ideas clearly. State the impact level boldly.
"""


def call_gemini(client: genai.Client, system_instruction: str, user_prompt: str) -> str:
    """Send the structured JSON to Gemini to generate the final note."""
    print(f"[Phase 3] Calling Gemini ({MODEL}) for Note Generation...")
    
    response = client.models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7, # Slightly higher temperature for creative phrasing
        ),
    )
    return response.text


def save_note(note_content: str, output_path: str) -> None:
    """Save the beautifully formatted markdown note."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(note_content)
    print(f"\n[Phase 3] Weekly Note saved successfully → {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load the analysis data
    analysis_data = load_analysis(ANALYSIS_PATH)

    # Convert the JSON payload to a formatted string for the prompt
    user_prompt = f"""
Please generate the weekly note based exactly on this structured data:

```json
{json.dumps(analysis_data, indent=2)}
```
"""

    # Init the Gemini Client
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Call Gemini to generate the creative note
    note_content = call_gemini(client, build_system_instruction(), user_prompt)

    # Output to console
    print("\n" + "═" * 60)
    print(note_content)
    print("═" * 60)

    # Word Count check warning (rough)
    word_count = len(note_content.split())
    if word_count > 250:
        print(f"\n[Phase 3] ⚠️ WARNING: The generated note is {word_count} words (limit is 250).")
    else:
        print(f"\n[Phase 3] 📏 Word count looks good: {word_count} words.")

    # Save to file
    save_note(note_content, OUTPUT_FILE)
    print("\n[Phase 3] Done. ✓")


if __name__ == "__main__":
    main()
