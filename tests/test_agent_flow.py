"""Tests for agent instruction generation and state transition logic."""

from unittest.mock import patch

from stella.agent import _build_step_instruction
from stella.models import MeasurementData, SessionState


def test_build_step_instruction_expertise_levels():
    """Verify that instruction generation incorporates user expertise levels."""
    state_prof = SessionState(user_expertise="professional")
    state_nov = SessionState(user_expertise="novice")

    instr_prof = _build_step_instruction(1, state_prof)
    instr_nov = _build_step_instruction(1, state_nov)

    assert "User Expertise Level: professional" in instr_prof
    assert "User Expertise Level: novice" in instr_nov
    assert "[STEP 1/4]" in instr_prof
    assert "[STEP 1/4]" in instr_nov


def test_build_step_instruction_with_context():
    """Verify that prior answers are summarized into subsequent turn instructions."""
    m = MeasurementData(bust_value=34, bust_unit="in", waist_value=26, waist_unit="in", hips_value=36, hips_unit="in", usual_size="S")
    m.normalize_measurements()

    state = SessionState(
        user_expertise="intermediate",
        measurements=m,
    )

    instr_q2 = _build_step_instruction(2, state)
    assert "size=S" in instr_q2
    assert "bust=34.0in (86.4cm)" in instr_q2
    assert "waist=26.0in (66.0cm)" in instr_q2


def test_build_step_instruction_followup_retry():
    """Verify follow-up instruction when a step is being retried."""
    state = SessionState(
        user_expertise="novice",
        attempts_per_step={1: 1},  # attempt 1 done, now retrying
    )
    instr_retry = _build_step_instruction(1, state)

    assert "[STEP 1/4 - FOLLOW-UP]" in instr_retry
    assert "Politely probe for more specific details" in instr_retry


def test_list_sessions_returns_valid_summaries(tmp_path):
    """Verify that list_sessions correctly reads saved session files and returns summary dicts."""
    from stella.agent import list_sessions, save_session

    state = SessionState(session_id="list_test_99", user_expertise="professional")
    state.current_step = 3
    state.confidence = 55.0

    with patch("stella.agent.get_settings") as mock_settings:
        mock_settings.return_value.sessions_dir = tmp_path
        save_session(state)

        summaries = list_sessions()
        assert len(summaries) == 1
        assert summaries[0]["session_id"] == "list_test_99"
        assert summaries[0]["user_expertise"] == "professional"
        assert summaries[0]["current_step"] == 3
        assert summaries[0]["confidence"] == 55.0
