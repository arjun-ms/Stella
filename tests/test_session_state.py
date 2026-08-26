"""Tests for SessionState modeling, JSON serialization, and transcript generation."""

import json
from stella.models import (
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)


def test_session_state_serialization_roundtrip():
    """Verify that SessionState models serialize to JSON and deserialize with fidelity."""
    m = MeasurementData(
        bust_value=88.0,
        bust_unit="cm",
        waist_value=68.0,
        waist_unit="cm",
        hips_value=94.0,
        hips_unit="cm",
        usual_size="US 4",
        detail_level="high",
    )
    m.normalize_measurements()

    state = SessionState(
        session_id="test1234",
        current_step=3,
        confidence=60.0,
        user_expertise="professional",
        measurements=m,
        fit_preference=FitPreferenceData(preference="structured sheath", detail_level="high"),
        style_occasion=StyleOccasionData(occasion="corporate awards gala", style="contemporary", detail_level="high"),
        past_purchase=PastPurchaseData(garment="Cocktail dress", brand="Theory", what_fit_well="Darted waist", detail_level="high"),
        attempts_per_step={1: 1, 2: 1, 3: 1},
    )
    state.add_message("assistant", "What are your body measurements?")
    state.add_message("user", "88cm bust, 68cm waist, 94cm hips, usually US 4")

    # Serialize to JSON
    json_str = state.model_dump_json(indent=2)
    assert "test1234" in json_str
    assert "professional" in json_str

    # Deserialize back
    restored = SessionState.model_validate_json(json_str)
    assert restored.session_id == state.session_id
    assert restored.user_expertise == "professional"
    assert restored.current_step == 3
    assert restored.confidence == 60.0
    assert restored.measurements is not None
    assert restored.measurements.bust_cm == 88.0
    assert restored.measurements.bust_in == 34.6
    assert len(restored.conversation_history) == 2


def test_transcript_formatting():
    """Verify transcript formatting output."""
    state = SessionState(session_id="trans_01")
    state.add_message("assistant", "Hello! Welcome to Stella.")
    state.add_message("user", "Hi Stella!")

    transcript = state.get_transcript()
    assert "Stella: Hello! Welcome to Stella." in transcript
    assert "User: Hi Stella!" in transcript


def test_state_dump_formatting():
    """Verify state dump output includes user expertise and dual unit formatting."""
    m = MeasurementData(
        bust_value=90.0,
        bust_unit="cm",
        waist_value=70.0,
        waist_unit="cm",
        hips_value=95.0,
        hips_unit="cm",
        detail_level="high",
    )
    m.normalize_measurements()

    state = SessionState(
        session_id="dump_01",
        user_expertise="novice",
        confidence=40.0,
        measurements=m,
    )
    dump = state.state_dump()

    assert "User Expertise: novice" in dump
    assert "Bust: 35.4 in (90.0 cm)" in dump
    assert "Waist: 27.6 in (70.0 cm)" in dump
    assert "Hips: 37.4 in (95.0 cm)" in dump
