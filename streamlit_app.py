"""Streamlit Web Application for Stella - AI Size & Fit Advisor.

Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from stella.agent import (
    _build_step_instruction,
    _get_chat_history,
    save_session,
    save_transcript,
)
from stella.config import ensure_api_key_configured, get_settings
from stella.export import export_html_dossier
from stella.llm import LLMClient
from stella.models import (
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)
from stella.scoring import compute_confidence

INITIAL_GREETING = (
    "✨ **Welcome to Stella — Your Personal Dress Size & Fit Stylist!** ✨\n\n"
    "I'll guide you through a quick 4-question consultation to recommend your exact dress size, "
    "ideal silhouettes, and tailored brand tips.\n\n"
    "**Question 1:** Could you share your bust, waist, and hips measurements? "
    "(You can share in inches, centimeters, or your usual off-the-rack brand size!)"
)


def init_session_state(session_dict: dict | None = None) -> SessionState:
    """Initialize or retrieve the Stella SessionState in streamlit session state."""
    if session_dict is None:
        session_dict = st.session_state

    if "stella_state" not in session_dict:
        state = SessionState()
        state.current_step = 1
        state.user_expertise = "novice"
        state.add_message("assistant", INITIAL_GREETING)
        session_dict["stella_state"] = state

    return session_dict["stella_state"]


def process_chat_turn(state: SessionState, user_input: str, llm: LLMClient) -> str:
    """Process a single turn of user input, extract structured data, and return assistant response."""
    state.add_message("user", user_input)
    current_step = state.current_step

    # Extract structured data
    try:
        extracted = llm.extract(current_step, user_input)
    except Exception:
        extracted = {"detail_level": "low"}

    # Update state based on step
    if current_step == 1:
        if state.measurements is None:
            state.measurements = MeasurementData()
        for k, v in extracted.items():
            if hasattr(state.measurements, k) and v is not None:
                setattr(state.measurements, k, v)
        state.measurements.normalize_measurements()

    elif current_step == 2:
        if state.fit_preference is None:
            state.fit_preference = FitPreferenceData()
        for k, v in extracted.items():
            if hasattr(state.fit_preference, k) and v is not None:
                setattr(state.fit_preference, k, v)

    elif current_step == 3:
        if state.style_occasion is None:
            state.style_occasion = StyleOccasionData()
        for k, v in extracted.items():
            if hasattr(state.style_occasion, k) and v is not None:
                setattr(state.style_occasion, k, v)

    elif current_step == 4:
        if state.past_purchase is None:
            state.past_purchase = PastPurchaseData()
        for k, v in extracted.items():
            if hasattr(state.past_purchase, k) and v is not None:
                setattr(state.past_purchase, k, v)

    # Recompute confidence
    state.confidence = compute_confidence(state)

    # If all 4 questions completed, generate recommendation
    if current_step >= 4:
        state.current_step = 5
        profile = {
            "user_expertise": state.user_expertise,
            "measurements": state.measurements.model_dump() if state.measurements else None,
            "fit_preference": state.fit_preference.model_dump() if state.fit_preference else None,
            "style_occasion": state.style_occasion.model_dump() if state.style_occasion else None,
            "past_purchase": state.past_purchase.model_dump() if state.past_purchase else None,
        }
        profile_json = json.dumps(profile, indent=2)
        try:
            assistant_reply = llm.recommend(5, profile_json)
        except Exception as e:
            assistant_reply = f"Failed to generate recommendation: {e}"
        state.add_message("assistant", assistant_reply)
    else:
        # Advance to next question
        state.current_step += 1
        instruction = _build_step_instruction(state.current_step, state)
        history = _get_chat_history(state)
        try:
            assistant_reply = llm.chat(state.current_step, instruction, history)
        except Exception as e:
            assistant_reply = f"Thank you! Could you share your thoughts for the next step? (Error: {e})"
        state.add_message("assistant", assistant_reply)

    # Persist session
    save_session(state)
    save_transcript(state)
    export_html_dossier(state)

    return assistant_reply


def main():
    st.set_page_config(
        page_title="Stella — AI Size & Fit Advisor",
        page_icon="👗",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS Styling
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0f1117;
            color: #f3f4f6;
        }
        .main-header {
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 2.2rem;
            font-weight: 700;
            color: #f48fb1;
            margin-bottom: 0.25rem;
        }
        .sub-header {
            color: #9ca3af;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }
        .stat-card {
            background: #181b24;
            border: 1px solid #282d3d;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }
        .stat-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #9ca3af;
            margin-bottom: 0.25rem;
        }
        .stat-val {
            font-size: 1.1rem;
            font-weight: 600;
            color: #38bdf8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    state = init_session_state(st.session_state)

    # Sidebar: Profile & Confidence Monitor
    with st.sidebar:
        st.markdown("### ✨ Stella Profile")
        st.caption(f"Session ID: `{state.session_id}`")

        # Expertise selector
        expertise_options = ["novice", "intermediate", "professional"]
        expertise_idx = expertise_options.index(state.user_expertise) if state.user_expertise in expertise_options else 0
        selected_expertise = st.selectbox(
            "Fashion Background",
            expertise_options,
            index=expertise_idx,
            format_func=lambda x: {
                "novice": "Novice (Plain English)",
                "intermediate": "Everyday Shopper",
                "professional": "Professional (Industry Terms)",
            }[x],
        )
        state.user_expertise = selected_expertise

        st.markdown("---")
        st.markdown("### 📊 Confidence Meter")
        conf = state.confidence
        st.progress(conf / 100.0)
        st.write(f"**Confidence: {conf:.1f}%**")

        st.markdown("---")
        st.markdown("### 📏 Extracted Measurements")
        m = state.measurements
        if m and (m.bust_in or m.bust_cm):
            b_in = f"{m.bust_in:.1f} in" if m.bust_in else "-"
            b_cm = f"{m.bust_cm:.1f} cm" if m.bust_cm else "-"
            w_in = f"{m.waist_in:.1f} in" if m.waist_in else "-"
            w_cm = f"{m.waist_cm:.1f} cm" if m.waist_cm else "-"
            h_in = f"{m.hips_in:.1f} in" if m.hips_in else "-"
            h_cm = f"{m.hips_cm:.1f} cm" if m.hips_cm else "-"

            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-title">Bust</div>
                    <div class="stat-val">{b_in} <span style="color:#9ca3af;font-size:0.9rem;">({b_cm})</span></div>
                    <div class="stat-title" style="margin-top:0.5rem;">Waist</div>
                    <div class="stat-val">{w_in} <span style="color:#9ca3af;font-size:0.9rem;">({w_cm})</span></div>
                    <div class="stat-title" style="margin-top:0.5rem;">Hips</div>
                    <div class="stat-val">{h_in} <span style="color:#9ca3af;font-size:0.9rem;">({h_cm})</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Awaiting measurements from Q1...")

        st.markdown("---")
        # Export Actions
        if state.current_step >= 5:
            dossier_path = Path("exports") / f"dossier_{state.session_id}.html"
            if dossier_path.exists():
                html_data = dossier_path.read_text(encoding="utf-8")
                st.download_button(
                    "📥 Download HTML Styling Dossier",
                    data=html_data,
                    file_name=f"stella_dossier_{state.session_id}.html",
                    mime="text/html",
                    use_container_width=True,
                )

        if st.button("🔄 Start New Consultation", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Main Chat View
    st.markdown('<h1 class="main-header">👗 Stella — AI Dress Size & Fit Advisor</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Multi-turn personal styling consultation powered by Google Gemini</p>', unsafe_allow_html=True)

    # Display chat message history
    for msg in state.conversation_history:
        with st.chat_message(msg.role, avatar="👗" if msg.role == "assistant" else "👤"):
            st.markdown(msg.content)

    # Chat Input
    if prompt := st.chat_input("Enter your response for Stella..."):
        # Display user message immediately
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # Initialize LLM client
        llm = LLMClient()
        llm.set_session_id(state.session_id)

        with st.chat_message("assistant", avatar="👗"):
            with st.spinner("✨ Stella is analyzing your profile..."):
                reply = process_chat_turn(state, prompt, llm)
                st.markdown(reply)

        st.rerun()


if __name__ == "__main__":
    main()
