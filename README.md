# Stella - AI Size & Fit Advisor

A multi-turn CLI chatbot that guides users through a personalized dress sizing and styling consultation using AI. Stella asks 4 targeted questions, extracts structured data from each answer, builds confidence in her recommendation, and delivers a tailored size/silhouette/brand recommendation.

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
├── models.py          # Pydantic models (session state, extracted data)
├── prompts.py         # Three system prompts
├── scoring.py         # Confidence score computation
├── display.py         # Rich-based terminal UI
├── llm.py             # Gemini API wrapper with tracing
└── config.py          # Settings and env loading
```

### Three-Prompt Architecture

Stella uses three separate system prompts, each with a distinct responsibility:

#### 1. Conversational Prompt (`CONVERSATION_PROMPT`)

Controls Stella's persona as a warm, knowledgeable personal stylist. This prompt:
- Defines the 4-question consultation flow and question ordering
- Sets tone (warm, encouraging, professional, uses fashion vocabulary)
- Instructs Stella to acknowledge previous answers before asking the next question
- Limits re-asking to once per question on vague answers
- Prohibits premature recommendations

**Why separated:** The conversational prompt needs to be rich with persona instructions and behavioral rules. Mixing extraction logic here would create conflicting objectives (be natural vs. be precise).

#### 2. Extraction Prompt (`EXTRACTION_PROMPT`)

Zero-personality prompt for structured data extraction. This prompt:
- Parses user answers into typed JSON matching Pydantic model schemas
- Classifies answer quality as `high`, `medium`, or `low` detail
- Never hallucinates data the user didn't provide
- Handles off-topic/nonsensical answers gracefully

**Why separated:** Extraction needs deterministic, analytical behavior with low temperature (0.1). The conversational prompt needs creativity with higher temperature (0.7). These are fundamentally different objectives.

#### 3. Recommendation Prompt (`RECOMMENDATION_PROMPT`)

Expert stylist delivering the final recommendation. This prompt:
- Synthesizes all collected profile data into actionable recommendations
- Generates: size range, dress silhouette, brand tip, and reasoning
- Calibrates confidence -- decisive when data is rich, broader when sparse
- Maintains Stella's warm tone

**Why separated:** The recommendation is a distinct task with different input (all 4 answers as structured data, not conversational history) and different output format. A dedicated prompt lets us inject the full profile as structured JSON context.

### State Flow

```
[Start] -> Welcome -> Q1 (Measurements)
                       |
                       v
                  Extract -> Low detail? -> Re-ask (max 1x)
                       |                         |
                       v                         v
                  Update confidence         Accept & proceed
                       |
                       v
                  Q2 (Fit Preference) -> ... -> Q3 -> Q4
                       |
                       v
                  [All data collected]
                       |
                       v
                  Generate Recommendation
                       |
                       v
                  Display + Save + Goodbye
```

Each turn involves:
1. **Conversational call** (Prompt 1): Generate Stella's question
2. **User input**: Read from terminal
3. **Extraction call** (Prompt 2): Parse answer into structured JSON
4. **Scoring**: Compute confidence based on detail level
5. **Decision**: Re-ask if vague (max 2 attempts), or advance

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

**Why heuristic:** A rule-based score is transparent, fast, deterministic, and easy to explain. The evaluator can see exactly why confidence went up or down. LLM-judged scores add latency and are opaque.

---

## Handling Ambiguity

When a user gives a vague or incomplete answer (e.g., "I'm medium-ish"):

1. **First attempt:** Stella acknowledges what they said, explains what additional detail would help, and politely re-asks
2. **Second attempt:** If still vague, Stella accepts the answer and moves on with whatever info was provided
3. **Confidence reflects it:** Vague answers contribute only 10% of that question's max points (via the `low` detail multiplier)
4. **Recommendation adapts:** Low-confidence profiles get broader recommendations with more size tolerance

The bot never crashes on bad input, never loops indefinitely, and never ignores what the user said.

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

- **Confidence score is gameable**: A user who gives specific-sounding but incorrect info (e.g., "my bust is 800 inches") will get high confidence. The extraction prompt tries to be faithful but doesn't validate physical plausibility.
- **Brand recommendations are training-data-bound**: Gemini's knowledge of brand sizing may be outdated or incomplete. No live inventory or sizing database is consulted.
- **No visual input**: Stella can't assess body type from photos, which a real stylist would consider.
- **Scoped to women's dresses**: The system doesn't generalize to other clothing types, menswear, or accessories.
- **No retailer-specific sizing**: Recommendations are general (US 6-8, A-line, etc.), not tied to specific retailers' size charts.
- **Single language**: English only. Non-English answers may produce poor extraction results.
- **Measurement unit handling is basic**: Supports inches and cm but doesn't auto-detect or validate plausible ranges.

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini API SDK |
| `pydantic` | Data models with validation and JSON serialization |
| `python-dotenv` | Load `.env` configuration |
| `rich` | Terminal UI (progress bars, panels, styled text) |
