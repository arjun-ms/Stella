"""Core agent loop for Stella - Size & Fit Advisor.

Orchestrates the 4-question consultation flow: asking questions via the
conversational prompt, extracting structured data, normalizing units,
computing confidence, and generating the final recommendation.
"""

from __future__ import annotations

import json
from pathlib import Path

from stella.config import ensure_api_key_configured, get_settings
from stella.display import (
    console,
    display_confidence_bar,
    display_error,
    display_goodbye,
    display_invalid_measurements_termination,
    display_measurement_guide,
    display_measurement_out_of_bounds_warning,
    display_quota_exhausted,
    display_recommendation,
    display_state_dump,
    display_stella_message,
    display_welcome,
    get_expertise_choice,
    get_user_input,
)
from stella.llm import LLMClient
from stella.models import (
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)
from stella.scoring import compute_confidence

# Maps step number to (question context description, Pydantic model class, state attribute name)
STEP_CONFIG: dict[int, tuple[str, type, str]] = {
    1: (
        "Measurements and size history: asking about body measurements (bust, waist, hips in inches, cm, or m) or typical dress size labels across brands",
        MeasurementData,
        "measurements",
    ),
    2: (
        "Fit preference: how the user likes dresses to fit (fitted, flowy, structured, relaxed, wrap, etc.) and any body concerns",
        FitPreferenceData,
        "fit_preference",
    ),
    3: (
        "Style and occasion: the event or setting the dress is for, and desired aesthetic",
        StyleOccasionData,
        "style_occasion",
    ),
    4: (
        "Past purchase that fit well: a specific dress or brand that worked, and what made it fit",
        PastPurchaseData,
        "past_purchase",
    ),
}

MAX_ATTEMPTS_PER_STEP = 2


def _get_chat_history(state: SessionState) -> list[dict]:
    """Convert session conversation history to the format expected by the LLM client."""
    return [
        {"role": msg.role, "content": msg.content}
        for msg in state.conversation_history
    ]


def _build_step_instruction(step: int, state: SessionState) -> str:
    """Build the user-facing instruction message for the conversational prompt."""
    context = STEP_CONFIG[step][0]
    attempt = state.attempts_per_step.get(step, 0)
    expertise = state.user_expertise or "intermediate"

    # Summarize what we already know for context
    known_parts: list[str] = []
    if state.measurements and step > 1:
        m = state.measurements
        known_parts.append(
            f"Measurements: size={m.usual_size}, "
            f"bust={m.bust_in}in ({m.bust_cm}cm), "
            f"waist={m.waist_in}in ({m.waist_cm}cm), "
            f"hips={m.hips_in}in ({m.hips_cm}cm)"
        )
    if state.fit_preference and step > 2:
        known_parts.append(f"Fit preference: {state.fit_preference.preference}")
    if state.style_occasion and step > 3:
        known_parts.append(f"Style/occasion: {state.style_occasion.occasion}, {state.style_occasion.style}")

    known_summary = "\n".join(known_parts) if known_parts else "None yet"

    if attempt == 0:
        step1_hint = ""
        if step == 1:
            step1_hint = (
                "Provide clear, friendly sample response formats to guide their answer "
                "(e.g. 'Bust: 34 in, Waist: 26 in, Hips: 36 in' or 'Bust: 88 cm, Waist: 68 cm, Hips: 92 cm'). "
                "Explicitly mention they can use inches (in), centimeters (cm), or meters (m).\n\n"
            )
        return (
            f"[STEP {step}/4]\n"
            f"User Expertise Level: {expertise}\n"
            f"Question Topic: {context}\n\n"
            f"{step1_hint}"
            f"Information collected so far:\n{known_summary}\n\n"
            f"Ask your question naturally, acknowledging any previous answers and calibrating your vocabulary to the user's expertise level."
        )
    else:
        unit_missing_hint = ""
        if step == 1 and state.measurements and state.measurements.needs_unit_confirmation():
            m = state.measurements
            b = m.bust_value if m.bust_value is not None else m.bust
            w = m.waist_value if m.waist_value is not None else m.waist
            h = m.hips_value if m.hips_value is not None else m.hips
            unit_missing_hint = (
                f"The user provided numbers for their measurements ({b}, {w}, {h}) "
                f"but did not specify the unit (inches, cm, or meters). Acknowledge their numbers warmly "
                f"and ask them to confirm whether these are in inches (in) or centimeters (cm).\n\n"
            )
        return (
            f"[STEP {step}/4 - FOLLOW-UP]\n"
            f"User Expertise Level: {expertise}\n"
            f"{unit_missing_hint}"
            f"Topic: {context}\n\n"
            f"Politely probe for more specific details. Be warm and encouraging. "
            f"This is your last chance to ask about this topic before moving on."
        )


def save_session(state: SessionState) -> Path:
    """Persist the session state to disk as JSON."""
    settings = get_settings()
    path = settings.sessions_dir / f"session_{state.session_id}.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_session(session_id: str) -> SessionState | None:
    """Load a session from disk by its ID."""
    settings = get_settings()
    path = settings.sessions_dir / f"session_{session_id}.json"
    if not path.exists():
        return None
    return SessionState.model_validate_json(path.read_text(encoding="utf-8"))


def save_transcript(state: SessionState) -> Path:
    """Save the conversation transcript to a text file."""
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)
    path = transcripts_dir / f"transcript_{state.session_id}.txt"
    path.write_text(state.get_transcript(), encoding="utf-8")
    return path


def run_consultation(
    state: SessionState | None = None,
    input_fn: callable | None = None,
) -> SessionState:
    """Run the full 4-question consultation flow.

    Args:
        state: Optional existing session to resume or pre-configure.
        input_fn: Optional callable for feeding user input programmatically.

    Returns:
        The final SessionState with recommendation delivered.
    """
    if state is None:
        state = SessionState()

    ensure_api_key_configured(input_fn)
    llm = LLMClient()
    llm.set_session_id(state.session_id)

    # Welcome & Onboarding for new sessions
    if state.current_step == 0:
        display_welcome()
        if not state.user_expertise:
            if input_fn is not None:
                state.user_expertise = "intermediate"
            else:
                state.user_expertise = get_expertise_choice()
        state.current_step = 1
        save_session(state)

    # Main consultation loop: steps 1-4
    while state.current_step <= 4:
        step = state.current_step
        question_context, model_class, attr_name = STEP_CONFIG[step]

        # Display measurement reference guide when asking Q1
        if step == 1 and state.attempts_per_step.get(1, 0) == 0:
            display_measurement_guide()

        # Initialize attempt counter for this step
        if step not in state.attempts_per_step:
            state.attempts_per_step[step] = 0

        # Generate Stella's question with interactive spinner
        instruction = _build_step_instruction(step, state)
        history = _get_chat_history(state)

        with console.status(
            f"[bold magenta]✨ Stella is preparing Question {step}/4...[/bold magenta]",
            spinner="dots",
        ):
            try:
                stella_response = llm.chat(step, instruction, history)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    display_quota_exhausted(state.session_id)
                else:
                    display_error(f"Failed to generate question: {e}")
                save_session(state)
                return state

        display_stella_message(stella_response)
        state.add_message("assistant", stella_response)

        # Get user input
        user_input = input_fn() if input_fn is not None else get_user_input()
        if not user_input:
            # User interrupted or EOF
            save_session(state)
            return state

        state.add_message("user", user_input)

        # Extract structured data from the answer with spinner
        schema = model_class.model_json_schema()
        with console.status(
            "[bold cyan]🔍 Analyzing your response & extracting styling details...[/bold cyan]",
            spinner="dots",
        ):
            try:
                extracted_data = llm.extract(step, user_input, question_context, schema)
            except Exception as e:
                display_error(f"Failed to process answer: {e}")
                # Move on with empty data rather than crashing
                extracted_data = {"detail_level": "low"}

        parsed = model_class.model_validate(extracted_data)

        # If step 1 (measurements), perform deterministic Python unit normalization & bounds check
        if isinstance(parsed, MeasurementData):
            parsed.normalize_measurements()
            is_out_of_bounds, issue_desc = parsed.has_out_of_bounds_measurements()
            if is_out_of_bounds:
                state.attempts_per_step[step] = state.attempts_per_step.get(step, 0) + 1
                if state.attempts_per_step[step] < MAX_ATTEMPTS_PER_STEP:
                    display_measurement_out_of_bounds_warning(issue_desc)
                    save_session(state)
                    continue
                else:
                    display_invalid_measurements_termination(state.session_id)
                    save_session(state)
                    return state

            # Check if user provided numbers without any unit (missing unit clarification)
            if parsed.needs_unit_confirmation() and state.attempts_per_step.get(step, 0) < MAX_ATTEMPTS_PER_STEP:
                state.attempts_per_step[step] = state.attempts_per_step.get(step, 0) + 1
                setattr(state, attr_name, parsed)
                confidence = compute_confidence(state)
                display_confidence_bar(confidence, step)
                save_session(state)
                continue

        # Check if we need to re-ask (vague answer, first attempt)
        state.attempts_per_step[step] = state.attempts_per_step.get(step, 0) + 1

        if parsed.detail_level == "low" and state.attempts_per_step[step] < MAX_ATTEMPTS_PER_STEP:
            # Store partial data but re-ask
            setattr(state, attr_name, parsed)
            confidence = compute_confidence(state)
            display_confidence_bar(confidence, step)
            save_session(state)
            continue  # Re-ask with follow-up instruction

        # Accept the answer and move to the next step
        setattr(state, attr_name, parsed)
        confidence = compute_confidence(state)
        display_confidence_bar(confidence, step)

        state.current_step = step + 1
        save_session(state)

    # Generate recommendation with animated spinner
    state.current_step = 5
    profile = {
        "user_expertise": state.user_expertise,
        "confidence_score": state.confidence,
        "measurements": state.measurements.model_dump() if state.measurements else None,
        "fit_preference": state.fit_preference.model_dump() if state.fit_preference else None,
        "style_occasion": state.style_occasion.model_dump() if state.style_occasion else None,
        "past_purchase": state.past_purchase.model_dump() if state.past_purchase else None,
    }
    profile_json = json.dumps(profile, indent=2)

    with console.status(
        "[bold magenta]✨ Stella is curating your personalized dress styling dossier & multi-unit sizing charts...[/bold magenta]",
        spinner="dots",
    ):
        try:
            recommendation = llm.recommend(5, profile_json)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                display_quota_exhausted(state.session_id)
            else:
                display_error(f"Failed to generate recommendation: {e}")
            save_session(state)
            return state

    display_recommendation(recommendation, state.confidence)
    state.add_message("assistant", recommendation)

    # Save everything
    save_session(state)
    transcript_path = save_transcript(state)
    from stella.export import export_html_dossier
    dossier_path = export_html_dossier(state)

    console.print(f"\n[bold green]📁 HTML Styling Dossier exported:[/bold green] [cyan]{dossier_path}[/cyan]\n")

    # Show final state dump
    display_state_dump(state.state_dump())
    display_goodbye()

    return state
