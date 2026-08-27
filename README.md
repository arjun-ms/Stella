# Stella - AI Size & Fit Advisor

A multi-turn CLI chatbot that guides users through a personalized dress sizing and styling consultation using AI. Stella asks 4 targeted questions, extracts structured data from each answer, normalizes mixed measurement units, dynamically adapts to user fashion expertise, builds confidence in her recommendation, and delivers a comprehensive size/silhouette/brand recommendation.

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd Stella

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
copy .env.example .env
# Edit .env and set your GOOGLE_API_KEY

# 5. Run Stella
python -m stella
```

### Resume a Session

```bash
python -m stella --resume <session-id>
```

### Inspect Session State

```bash
python -m stella --dump <session-id>
```

### Export Standalone HTML Styling Dossier

```bash
python -m stella --export <session-id>
```
*Generates a self-contained, responsive, print-ready HTML Lookbook Dossier in `exports/dossier_<id>.html`.*

### Launch Streamlit Web UI (Bonus)

```bash
streamlit run streamlit_app.py
```
*Launches an interactive browser UI with real-time confidence gauge, extracted measurement cards, chat bubbles, and instant dossier download.*

### Run Test Suite

```bash
pytest -v
```

---

## Key Features & Highlights

### 1. Tailored Expertise Onboarding (Step 0)
At session launch, users select their background:
- **[a] Professional / Industry Insider:** Technical styling vocabulary (darting, bias cut, ease, fabrication).
- **[b] Fashion Novice:** Simple, welcoming, plain-language guidance without industry jargon.
- **[c] Everyday Shopper:** Practical, actionable fit advice with intuitive explanations.

### 2. Built-in Measurement Guide & Size Reference Table (Q1)
- Rich terminal table displaying how to measure bust, waist, and hips.
- Reference chart mapping XS–XL, US 0–18, and bust-waist-hips ranges in both inches and centimeters.
- Clear support for off-the-rack size labels if physical measurements are unavailable.

### 3. Deterministic Mixed-Unit Normalization & Multi-Unit Recommendations
- Supports mixed inputs (e.g., *Bust: 90cm, Waist: 0.7m, Hips: 36 inches*).
- Deterministic Python math normalizes all inputs into standardized dual representations (`inches` & `cm`).
- Final recommendation provides complete multi-unit sizing (US, UK, EU, International Alpha XS-XL, and garment dimensions in both inches and cm).

### 4. Interactive UX Loading Spinners
- Rich `console.status` animated spinners during all AI reasoning and extraction turns prevent perceived UI freezes.

---

## Model Choice & Cascade Resilience

**Primary Active Model:** `gemini-3.5-flash`
**Automatic Fallback Cascade:** `["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]`

**Why:**
- Fast generation (typically 400–700ms) with strong instruction and persona following.
- Native structured JSON schema output via `response_mime_type="application/json"` and Pydantic validation.
- **Ordered Quota Failover**: If the active model exhausts its daily free tier quota (HTTP 429), Stella automatically fails over to the next configured model in the cascade with a clean user notice (`🔄 Model 'X' quota exhausted. Switching to fallback model 'Y'...`).
- **Dynamic Rate-Limit Retry**: If transient Google rate limits occur, Stella dynamically parses `retry in Xs`, displays a real-time yellow countdown notice, and pauses before retrying (up to 6 attempts with exponential backoff).
- **Graceful Quota Handling**: If all models in the cascade exhaust their quotas, Stella cleanly saves session state to disk, displays a friendly guidance panel, and exits without stack traces.

---

## Key Features & Highlights

### 1. Tailored Expertise Onboarding (Step 0)
At session launch, users select their background:
- **[a] Professional / Industry Insider:** Technical styling vocabulary (darting, bias cut, ease, fabrication).
- **[b] Fashion Novice:** Simple, welcoming, plain-language guidance without industry jargon.
- **[c] Everyday Shopper:** Practical, actionable fit advice with intuitive explanations.

### 2. Built-in Measurement Guide & Size Reference Table (Q1)
- Rich terminal table displaying how to measure bust, waist, and hips.
- Reference chart mapping XS–XL, US 0–18, and bust-waist-hips ranges in both inches and centimeters.
- Clear support for off-the-rack size labels if physical measurements are unavailable.

### 3. Inclusive Validation & Outlier Proportions
- Embraces all genuine human body diversity and outlier shapes (petite 14–22 in waists, extended plus sizes up to 120+ in, maternity, and athletic builds).
- Detects non-positive ($\le 0$) or physically impossible numbers (e.g. 999 meters); gives a polite 2nd chance retry before concluding the session gracefully.

### 4. Zero-Assumption Unit Clarification
- If a user enters raw numbers without units (e.g. `34 26 36`), Stella avoids blind guessing and asks a polite conversational follow-up to confirm whether the numbers are inches or centimeters.

### 5. Deterministic Mixed-Unit Normalization & Multi-Unit Recommendations
- Supports mixed inputs (e.g., *Bust: 90cm, Waist: 0.7m, Hips: 36 inches*).
- Deterministic Python math normalizes all inputs into standardized dual representations (`inches` & `cm`).
- Final recommendation provides complete multi-unit sizing (US, UK, EU, International Alpha XS-XL, and garment dimensions in both inches and cm).

### 6. Interactive UX Loading Spinners & Windows UTF-8 Support
- Rich `console.status` animated spinners during all AI reasoning and extraction turns prevent perceived UI freezes.
- Cross-platform UTF-8 terminal configuration prevents character encoding crashes on Windows PowerShell and CMD.

---

## Architecture

### Project Structure

```
stella/
├── __init__.py        # Package init
├── __main__.py        # CLI entry point (python -m stella)
├── agent.py           # Core agent loop and orchestration
├── models.py          # Pydantic models (session state, multi-unit normalization, bounds)
├── prompts.py         # Three system prompts (conversation, extraction, recommendation)
├── scoring.py         # Confidence score computation
├── display.py         # Rich-based terminal UI, guide tables, error banners, & onboarding
├── llm.py             # Gemini API wrapper with tracing, cascade failover, & retry backoff
└── config.py          # Settings, cascade model list, and env loading
```

### Three-Prompt Architecture

Stella uses three separate system prompts, each with a distinct responsibility:

#### 1. Conversational Prompt (`CONVERSATION_PROMPT`)

Controls Stella's persona as a warm, knowledgeable personal stylist. This prompt:
- Calibrates vocabulary to the user's selected expertise level (professional, novice, intermediate)
- Defines the 4-question consultation flow and question ordering
- Explicitly welcomes measurements in any unit (inches, cm, or meters) with example formats
- Instructs Stella to acknowledge previous answers before asking the next question
- Limits re-asking to once per question on vague answers or missing units
- Prohibits premature recommendations

#### 2. Extraction Prompt (`EXTRACTION_PROMPT`)

Zero-personality prompt for structured data extraction. This prompt:
- Parses user answers into typed JSON matching Pydantic model schemas
- Captures raw measurement values and per-field units (in, cm, m)
- Avoids guessing units when user omits them (sets units to `null` to trigger clarification)
- Classifies answer quality as `high`, `medium`, or `low` detail
- Never hallucinates data the user didn't provide
- Handles off-topic/nonsensical answers gracefully

#### 3. Recommendation Prompt (`RECOMMENDATION_PROMPT`)

Expert stylist delivering the final recommendation. This prompt:
- Synthesizes all collected profile data into actionable recommendations
- Generates: comprehensive multi-unit size breakdown (US, UK, EU, XS-XL, in, cm), dress silhouettes, brand tips, and styling rationale
- Calibrates confidence and vocabulary to user background

---

## State Flow & Ambiguity Handling

```
[Start] -> Welcome -> Step 0: Expertise Selection (a/b/c)
                       |
                       v
            Step 1: Measurement Guide + Q1 (in / cm / m)
                       |
                       v
                  Extract JSON -> Unit Normalization
                       |
          ┌────────────┴────────────┐
          │                         │
     [Unit Missing]         [Out of Bounds]
          │                         │
          v                         v
     (Follow-up probe)         (2nd chance warning -> Polite exit)
          │                         │
          └────────────┬────────────┘
                       │
                       v
                  Update Confidence Meter
                       |
                       v
            Step 2: Q2 (Fit Preference) -> Step 3: Q3 -> Step 4: Q4
                       |
                       v
                  [All data collected]
                       |
                       v
                  Generate Multi-Unit Styling Dossier
                       |
                       v
                  Display + Save JSON + Save Transcript + State Dump
```

### Confidence Scoring

The confidence score (0–100%) is deterministic and computed from the detail level of each extracted answer:

| Question | Max Points | What Earns Full Points |
|---|---:|---|
| Q1: Measurements | 40 | Specific measurements with units or exact size + brand reference |
| Q2: Fit Preference | 20 | Clear preference + body area concerns |
| Q3: Style & Occasion | 15 | Specific occasion + aesthetic preference |
| Q4: Past Purchase | 25 | Named garment/brand + what fit well |

Detail level multipliers:
- **High** (1.0x): Specific numbers, brand names, clear preferences
- **Medium** (0.6x): General but useful info ("usually a Medium")
- **Low** (0.2x): Vague, off-topic, or minimal info

---

## Automated Test Suite (33 Tests)

Run the full test suite with pytest:
```bash
pytest -v
```

The test suite covers 5 distinct domains:
1. **Agent Flow & Calibration (`test_agent_flow.py`)**: Context summarization, expertise prompt generation, follow-up retries.
2. **Deterministic Normalization (`test_normalization.py`)**: Centimeters, meters, inches, mixed units, and null safety.
3. **Confidence Scoring (`test_scoring.py`)**: 100-point weight distribution, high/medium/low multipliers.
4. **Session Persistence (`test_session_state.py`)**: JSON state roundtrips, transcript formatting, state dumps.
5. **Failure Mode Resilience (`test_failure_modes.py`)**: API crashes, malformed JSON recovery, rate-limit retry notices, model cascade failover, total quota banners, impossible number termination, human outlier acceptance, missing unit follow-up.
6. **End-to-End Persona Scenarios (`test_e2e_scenarios.py`)**: Multi-turn full runs for Novice, Professional Metric, Petite Outlier, Plus Size Curve, and Unit Recovery.

---

## Bonus Features

### Session Persistence & Transcripts
- Sessions saved as JSON to `sessions/session_<id>.json` after every step. Resume with `python -m stella --resume <session-id>`.
- Formatted transcripts saved to `transcripts/transcript_<id>.txt`.

### LLM Call Tracing
Every API call is logged to `logs/trace_{session_id}.jsonl` with timestamps, call types, model names, latency in milliseconds, and token counts.

---

## Known Limitations

- **Live Retailer Inventory**: Brand recommendations and sizing suggestions are synthesized from LLM fashion knowledge without querying live e-commerce inventory or stock APIs.
- **No Visual Computer Vision**: Stella evaluates sizing conversationally and cannot ingest user photos or webcam feeds.
- **Domain Scope**: Stella specializes exclusively in women's dresses and does not generalize to menswear or suiting.
- **Language**: Consultation prompts are optimized for English. Non-English responses may yield lower extraction confidence.
