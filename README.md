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

## Model Choice

**Model:** `gemini-2.5-flash` (Google Gemini)

**Why:** Gemini 2.5 Flash offers the best balance of quality, speed, and cost for a conversational chatbot:
- Strong instruction following for persona maintenance across turns
- Fast response times (typically 400-800ms per call) for interactive CLI use
- Native structured JSON output via `response_mime_type` and `response_schema`, eliminating fragile regex parsing
- Cost-effective for a prototype that makes 2-3 API calls per question turn

---

## Architecture

### Project Structure

```
stella/
├── __init__.py        # Package init
├── __main__.py        # CLI entry point (python -m stella)
├── agent.py           # Core agent loop and orchestration
├── models.py          # Pydantic models (session state, multi-unit data)
├── prompts.py         # Three system prompts (conversation, extraction, recommendation)
├── scoring.py         # Confidence score computation
├── display.py         # Rich-based terminal UI, guide tables, & onboarding
├── llm.py             # Gemini API wrapper with tracing
└── config.py          # Settings and env loading
```

### Three-Prompt Architecture

Stella uses three separate system prompts, each with a distinct responsibility:

#### 1. Conversational Prompt (`CONVERSATION_PROMPT`)

Controls Stella's persona as a warm, knowledgeable personal stylist. This prompt:
- Calibrates vocabulary to the user's selected expertise level (professional, novice, intermediate)
- Defines the 4-question consultation flow and question ordering
- Explicitly welcomes measurements in any unit (inches, cm, or meters)
- Instructs Stella to acknowledge previous answers before asking the next question
- Limits re-asking to once per question on vague answers
- Prohibits premature recommendations

#### 2. Extraction Prompt (`EXTRACTION_PROMPT`)

Zero-personality prompt for structured data extraction. This prompt:
- Parses user answers into typed JSON matching Pydantic model schemas
- Captures raw measurement values and per-field units (in, cm, m)
- Classifies answer quality as `high`, `medium`, or `low` detail
- Never hallucinates data the user didn't provide
- Handles off-topic/nonsensical answers gracefully

#### 3. Recommendation Prompt (`RECOMMENDATION_PROMPT`)

Expert stylist delivering the final recommendation. This prompt:
- Synthesizes all collected profile data into actionable recommendations
- Generates: comprehensive multi-unit size breakdown (US, UK, EU, XS-XL, in, cm), dress silhouettes, brand tips, and styling rationale
- Calibrates confidence and vocabulary to user background

### State Flow

```
[Start] -> Welcome -> Step 0: Expertise Selection (a/b/c)
                       |
                       v
            Step 1: Measurement Guide + Q1 (Measurements in in/cm/m)
                       |
                       v
                  Extract -> Unit Normalization (Python) -> Low detail? -> Re-ask (max 1x)
                       |                                                |
                       v                                                v
                  Update confidence                                Accept & proceed
                       |
                       v
            Step 2: Q2 (Fit Preference) -> Step 3: Q3 -> Step 4: Q4
                       |
                       v
                  [All data collected]
                       |
                       v
                  Generate Multi-Unit Recommendation
                       |
                       v
                  Display + Save + State Dump + Goodbye
```

### Confidence Scoring

The confidence score (0-100%) is heuristic-based, computed from the detail level of each extracted answer:

| Question | Max Points | What Earns Full Points |
|---|---:|---|
| Q1: Measurements | 40 | Specific measurements or exact size + brand reference |
| Q2: Fit Preference | 20 | Clear preference + body area concerns |
| Q3: Style & Occasion | 15 | Specific occasion + aesthetic preference |
| Q4: Past Purchase | 25 | Named garment/brand + what fit well |

Detail level multipliers:
- **High** (1.0x): Specific numbers, brand names, clear preferences
- **Medium** (0.6x): General but useful info ("usually a Medium")
- **Low** (0.1x): Vague, off-topic, or no useful info

---

## Handling Ambiguity

When a user gives a vague or incomplete answer (e.g., "I'm medium-ish"):

1. **First attempt:** Stella acknowledges what they said, explains what additional detail would help, and politely re-asks
2. **Second attempt:** If still vague, Stella accepts the answer and moves on with whatever info was provided
3. **Confidence reflects it:** Vague answers contribute only 10% of that question's max points (via the `low` detail multiplier)
4. **Recommendation adapts:** Low-confidence profiles get broader recommendations with more size tolerance

---

## Bonus Features

### Session Persistence

Sessions are saved as JSON to `sessions/` after every step. Resume with:
```bash
python -m stella --resume <session-id>
```
The session ID is displayed at startup and in the state dump.

### LLM Call Tracing

Every API call is logged to `logs/trace_{session_id}.jsonl` with:
- Timestamp
- Call type (conversation / extraction / recommendation)
- Model name
- Step number
- Latency in milliseconds
- Token counts (prompt, completion, total)

---

## Known Limitations

- **Physical plausibility bounds**: A user who gives extreme numbers (e.g., "bust is 500 inches") is normalized mathematically without medical/anatomical sanity rejection.
- **Brand recommendations are training-data-bound**: Gemini's knowledge of brand sizing may be outdated or incomplete. No live retailer inventory is queried.
- **No visual input**: Stella can't assess body type from photos, which an in-person stylist might do.
- **Scoped to women's dresses**: The system is specialized for women's dresses and does not generalize to menswear or suiting.
- **Single language**: English only. Non-English answers may produce poor extraction results.
