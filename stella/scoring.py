"""Confidence score computation module for Stella.

Calculates the session confidence score based on the detail level and completeness
of user-provided information across the 4-step consultation flow.
"""

from __future__ import annotations

from stella.models import (
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)

# Maximum points allocated to each question step (Total = 100)
SCORING_WEIGHTS: dict[int, float] = {
    1: 40.0,  # Q1: Measurements and sizing history
    2: 20.0,  # Q2: Fit preference and body concerns
    3: 15.0,  # Q3: Style and occasion
    4: 25.0,  # Q4: Past purchase reference
}

# Multiplier applied to step weight based on extracted detail level
DETAIL_MULTIPLIERS: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.1,
}


def compute_question_score(
    step: int,
    data: MeasurementData | FitPreferenceData | StyleOccasionData | PastPurchaseData,
) -> float:
    """Compute the points earned for a single question step.

    Calculated as the product of the question weight and the detail level multiplier:
    `SCORING_WEIGHTS[step] * DETAIL_MULTIPLIERS[data.detail_level]`

    Args:
        step: Question step number (1 to 4).
        data: Extracted data model containing a detail_level field ('high', 'medium', or 'low').

    Returns:
        float: Points earned for the question (clamped to at least 0.0).
    """
    weight = SCORING_WEIGHTS.get(step, 0.0)
    multiplier = DETAIL_MULTIPLIERS.get(data.detail_level, 0.0)
    return round(weight * multiplier, 2)


def compute_confidence(state: SessionState) -> float:
    """Calculate and update the total confidence score for a session.

    Iterates over all filled-in question data models in the session state,
    sums the earned scores, clamps the total between 0.0 and 100.0,
    updates `state.confidence` in-place, and returns the calculated score.

    Args:
        state: The current SessionState object to evaluate and update.

    Returns:
        float: Total confidence score clamped to range [0.0, 100.0].
    """
    step_data_pairs: list[
        tuple[
            int,
            MeasurementData | FitPreferenceData | StyleOccasionData | PastPurchaseData | None,
        ]
    ] = [
        (1, state.measurements),
        (2, state.fit_preference),
        (3, state.style_occasion),
        (4, state.past_purchase),
    ]

    total_score = 0.0
    for step, data in step_data_pairs:
        if data is not None:
            total_score += compute_question_score(step, data)

    clamped_score = max(0.0, min(100.0, round(total_score, 2)))
    state.confidence = clamped_score
    return clamped_score
