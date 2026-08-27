"""Tests for the Streamlit Web UI integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from stella.models import MeasurementData, SessionState


def test_streamlit_state_initialization():
    """Verify that Streamlit helper correctly initializes a new SessionState."""
    from streamlit_app import init_session_state

    mock_session_state = {}
    init_session_state(mock_session_state)

    assert "stella_state" in mock_session_state
    state = mock_session_state["stella_state"]
    assert isinstance(state, SessionState)
    assert state.current_step == 1
    assert len(state.conversation_history) >= 1


def test_streamlit_process_user_message():
    """Verify that Streamlit helper processes user input, extracts data, updates confidence,
    and advances the conversation step."""
    from streamlit_app import process_chat_turn

    state = SessionState(session_id="st_test_1", user_expertise="novice")
    state.current_step = 1

    with patch("streamlit_app.LLMClient") as mock_client_cls:
        mock_llm = MagicMock()
        mock_llm.extract.return_value = {
            "bust_value": 34.0,
            "waist_value": 26.0,
            "hips_value": 36.0,
            "unit": "in",
            "usual_size": "US 4",
            "size_brand_ref": "Zara",
            "detail_level": "high",
        }
        mock_llm.chat.return_value = "Great measurements! How do you like your dresses to fit?"
        mock_client_cls.return_value = mock_llm

        reply = process_chat_turn(state, "My bust is 34 inches, waist is 26 inches, hips 36 inches", mock_llm)

        assert state.current_step == 2
        assert state.measurements.bust_in == 34.0
        assert state.measurements.bust_cm == 86.4
        assert state.confidence == 40.0
        assert "Great measurements" in reply


def test_streamlit_rate_limit_status_callback_forwarding():
    """Verify that Streamlit helper configures status callback on LLMClient to capture rate limits."""
    from streamlit_app import process_chat_turn

    state = SessionState(session_id="st_test_2", user_expertise="novice")
    state.current_step = 1

    mock_llm = MagicMock()
    mock_llm.extract.return_value = {"detail_level": "low"}
    mock_llm.chat.return_value = "Let's move on."

    status_events = []
    def capture_status(level, msg):
        status_events.append((level, msg))

    # When set_status_callback is called, test that it accepts the function
    process_chat_turn(state, "I wear medium", mock_llm, status_callback=capture_status)

    mock_llm.set_status_callback.assert_called_once()


def test_streamlit_quota_exhausted_graceful_handling():
    """Verify that when all models hit 429 quota exhaustion, Streamlit turn catches it cleanly."""
    from streamlit_app import process_chat_turn

    state = SessionState(session_id="st_test_quota", user_expertise="novice")
    state.current_step = 1

    mock_llm = MagicMock()
    mock_llm.extract.return_value = {"detail_level": "low"}
    mock_llm.chat.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED: Daily quota reached")

    reply = process_chat_turn(state, "34 bust", mock_llm)

    assert "quota" in reply.lower() or "limit" in reply.lower()
    assert state.session_id == "st_test_quota"

