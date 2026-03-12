"""
Phase 4: Dashboard UI Implementation
INDMoney App Review Insights Analyser

A Streamlit dashboard to securely display the Weekly Insights Note
without exposing raw data or any PII.
"""

import os
from pathlib import Path
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

# Ensure the page config is the first Streamlit command
st.set_page_config(
    page_title="INDMoney Insights",
    page_icon="💸",
    layout="centered",
)

NOTE_PATH = Path("../phase3/weekly_insight_note.md")


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_markdown_note(path: Path) -> str:
    """Load the finalized Markdown note from Phase 3."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── UI ────────────────────────────────────────────────────────────────────────

def main():
    st.title("💸 INDMoney App Review Insights")
    st.markdown("---")
    
    st.write(
        "Welcome to the PM Dashboard. Here is the latest auto-generated insights report "
        "synthesized from public Google Play Store reviews."
    )
    
    # 1. Load the note
    note_content = load_markdown_note(NOTE_PATH)
    
    if not note_content:
        st.warning("⚠️ No weekly report found. Please ensure Phases 1, 2, and 3 have been executed successfully.")
        st.stop()
        
    # 2. Display the Note Container (Simulating a beautiful email / document layout)
    with st.container(border=True):
        st.markdown(note_content)
        
    st.markdown("---")
    
    # 3. Action Buttons
    cols = st.columns([1, 1, 2])
    
    with cols[0]:
        # Phase 5 hook (we'll implement the actual email sending soon)
        if st.button("📧 Email Report", type="primary", use_container_width=True):
            st.info("Email distribution (Phase 5) will be triggered here!")
            
    with cols[1]:
        if st.button("🔄 Regenerate", use_container_width=True):
            st.info("Triggering the pipeline (Phases 1-3) can be connected here.")
            
    # Privacy reminder footer
    st.caption("🔒 **Privacy Controls Active:** This dashboard only displays aggregated and anonymized AI outputs. No raw reviews, usernames, or Personally Identifiable Information (PII) are accessible here or retained in memory.")

if __name__ == "__main__":
    main()
