# INDMoney App Review Insights Analyser Architecture

## Project Overview
**App:** INDMoney (App ID: `in.indwealth`)
**Goal:** Automate the extraction of public app reviews, analyze them for key themes using Groq LLM, and generate a concise weekly insights report to drive product actions, all while strictly preserving user privacy (No PII).

## Constraints & Requirements
1. **Public Data Only:** Scraping limited to public reviews using `google-play-scraper`; no authenticated scraping.
2. **Theme Limitation:** Reviews must be categorized into a maximum of 5 themes (e.g., Onboarding, KYC, Payments, Statements, Withdrawals).
3. **Report Format:** Scannable, one-page weekly note (≤ 250 words) detailing Top 3 themes, 3 user quotes, and 3 action ideas.
4. **Privacy First:** Absolutely NO Personally Identifiable Information (PII) like usernames, emails, or IDs in any artifacts or reports.

---

## Phase 1: Data Acquisition & Preprocessing
**Objective:** Fetch, filter, and clean data for the last 6 weeks.

- **Data Source:** Google Play Store.
- **Tooling:** Python with `google-play-scraper` package.
- **Process:**
  1. **Fetch Data:** Execute a weekly scheduled script to scrape reviews for `in.indwealth`. Extract specifically: `score` (rating), `title`, `content` (text), and `at` (date).
  2. **Time Filtering:** Filter the dataset to include only reviews from the exact rolling 6-week window.
  3. **Data Anonymization (PII Stripping):** 
     - Explicitly drop reviewer names, IDs, and avatars during the extraction phase.
     - Run a lightweight regex pass on `title` and `content` to redact potential accidental PII leaks (e.g., PAN numbers, phone numbers, email addresses).
  4. **Staging:** Store the sanitized data transiently in a local structured format (e.g., JSON or in-memory DataFrame) for LLM processing.

## Phase 2: AI-Powered Thematic Analysis
**Objective:** Group the sanitized reviews into themes and extract insights using Groq.

- **AI/LLM Engine:** Groq (leveraging fast inference APIs, e.g., using Llama 3).
- **Process:**
  1. **Prompt Engineering:** Formulate a strict system prompt for Groq with the weekly sanitized data.
     - *Constraint 1:* Categorize all provided reviews into exactly 5 predefined themes (e.g., Onboarding, KYC, Payments, App Performance, Customer Support).
     - *Constraint 2:* Identify the Top 3 most frequently mentioned themes.
     - *Constraint 3:* Extract 3 highly representative, anonymized user quotes.
     - *Constraint 4:* Generate 3 specific, actionable product ideas based on the feedback.
  2. **Data Extraction:** Parse Groq's response into a structured JSON schema validating the Top 3 themes, 3 quotes, and 3 ideas.

## Phase 3: Note Generation & Formatting
**Objective:** Compile the processed AI output into a creative, scannable, constrained text format using Gemini.

- **AI/LLM Engine:** Google Gemini (e.g., Gemini 1.5 Flash) for creative and concise formatting.
- **Process:**
  1. **Prompt Engineering:** Pass the structured JSON from Phase 2 to Gemini with strict instructions to generate a one-page note.
  2. **Word Count Validation:** Instruct Gemini to keep the finalized report text strictly ≤ 250 words to maintain strict scannability.
  3. **Creative Assembly:** Have Gemini populate the final one-page note structure with an engaging tone. Expected outline:
     - **Headline:** Weekly INDMoney App Review Insights
     - **Top 3 Themes:** [Theme 1], [Theme 2], [Theme 3]
     - **Voice of Customer (3 Quotes):** "[Quote 1]", "[Quote 2]", "[Quote 3]"
     - **Action Items (3 Ideas):** [Idea 1], [Idea 2], [Idea 3]

## Phase 4: Dashboard UI Implementation
**Objective:** Create an interactive web interface to view the generated insights and trigger actions.

- **Tooling:** Python with `streamlit` library.
- **Process:**
  1. **Insights Display:** Build a clean, single-page Streamlit dashboard to cleanly render the weekly one-page note (Top 3 themes, 3 quotes, 3 ideas).
  2. **On-Demand Generation & Review:** Provide functionality to manually trigger the scraping/analysis pipeline, or preview the generated note before dispatch.
  3. **Privacy Controls:** Ensure the UI strictly shows the aggregated AI output and does not expose raw reviews or any PII.

## Phase 5: Final Distribution
**Objective:** Draft and send the weekly note to the PM or alias securely.

- **Tooling:** Python `smtplib` or transactional email API (e.g., AWS SES, SendGrid).
- **Process:**
  1. **Email Drafting:** Inject the assembled 250-word note into the body of a standard email. 
  2. **Delivery:** Dispatch to the designated product alias (e.g., `akshat.lallan678@gmail.com`) or self. This trigger can also be integrated directly as a "Send Email" button within the Streamlit UI.
  3. **Security Cleanup:** Hard delete any local transient files (JSON/CSVs) that stored the weekly batch of reviews to maintain a zero-retention privacy policy.

## Phase 6: Automated Scheduling
**Objective:** Automate the entire pipeline to run weekly without manual intervention.

- **Tooling:** GitHub Actions.
- **Process:**
  1. **Orchestration Script:** Create a `main.py` script to run Phases 1, 2, 3, and 5 in sequence.
  2. **GitHub Workflow:** Define a `.github/workflows/weekly_pulse.yml` file.
  3. **Schedule:** Configure a `cron` schedule to trigger every Thursday at 3:00 PM IST (09:30 UTC).
  4. **Secrets Management:** Use GitHub Repository Secrets to store Groq API Key, Gemini API Key, and Email Credentials securely.
