"""Tests for confidence scoring engine in Stella."""

import pytest
from stella.models import (
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)
from stella.scoring import (
    DETAIL_MULTIPLIERS,
    SCORING_WEIGHTS,
    compute_confidence,
    compute_question_score,
)


def test_scoring_weights_total_100():
    """Verify that the sum of maximum weights across steps 1-4 equals 100."""
    total = sum(SCORING_WEIGHTS.values())
    assert total == 100.0


def test_question_score_detail_levels():
    """Verify points earned for high, medium, and low detail levels on Q1."""
    data_high = MeasurementData(bust=34, waist=26, hips=36, detail_level="high")
    data_med = MeasurementData(usual_size="M", detail_level="medium")
    data_low = MeasurementData(detail_level="low")

    score_high = compute_question_score(1, data_high)
    score_med = compute_question_score(1, data_med)
    score_low = compute_question_score(1, data_low)

    assert score_high == 40.0 * 1.0  # 40.0
    assert score_med == 40.0 * 0.6   # 24.0
    assert score_low == 40.0 * 0.1   # 4.0


def test_confidence_progression_high_detail():
    """Verify incremental confidence updates as steps 1-4 are completed with high detail."""
    state = SessionState()
    assert compute_confidence(state) == 0.0

    # Step 1: Measurements (max 40 pts)
    state.measurements = MeasurementData(bust=34, waist=26, hips=36, detail_level="high")
    assert compute_confidence(state) == 40.0

    # Step 2: Fit preference (max 20 pts)
    state.fit_preference = FitPreferenceData(preference="A-line fitted bodice", detail_level="high")
    assert compute_confidence(state) == 60.0

    # Step 3: Style & Occasion (max 15 pts)
    state.style_occasion = StyleOccasionData(occasion="Black tie gala", style="Minimalist", detail_level="high")
    assert compute_confidence(state) == 75.0

    # Step 4: Past purchase (max 25 pts)
    state.past_purchase = PastPurchaseData(garment="Wrap midi", brand="Diane von Furstenberg", what_fit_well="Silk jersey stretch", detail_level="high")
    assert compute_confidence(state) == 100.0


def test_confidence_mixed_detail_levels():
    """Verify confidence with mixed detail levels across turns."""
    state = SessionState(
        measurements=MeasurementData(usual_size="S", detail_level="medium"),  # 40 * 0.6 = 24
        fit_preference=FitPreferenceData(preference="flowy", detail_level="medium"),  # 20 * 0.6 = 12
        style_occasion=StyleOccasionData(occasion="wedding", detail_level="medium"),  # 15 * 0.6 = 9
        past_purchase=PastPurchaseData(detail_level="low"),  # 25 * 0.1 = 2.5
    )
    # Expected: 24 + 12 + 9 + 2.5 = 47.5
    assert compute_confidence(state) == 47.5
