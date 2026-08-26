"""Tests for measurement unit normalization in Stella."""

import pytest
from stella.models import MeasurementData


def test_inches_normalization():
    """Test standard inch measurements."""
    data = MeasurementData(
        bust_value=36.0,
        bust_unit="inches",
        waist_value=28.0,
        waist_unit="in",
        hips_value=38.0,
        hips_unit="inch",
    )
    data.normalize_measurements()

    assert data.bust_in == 36.0
    assert data.bust_cm == round(36.0 * 2.54, 1)
    assert data.waist_in == 28.0
    assert data.waist_cm == round(28.0 * 2.54, 1)
    assert data.hips_in == 38.0
    assert data.hips_cm == round(38.0 * 2.54, 1)
    assert data.unit == "inches"
    assert data.bust == 36.0


def test_centimeters_normalization():
    """Test standard cm measurements."""
    data = MeasurementData(
        bust_value=90.0,
        bust_unit="cm",
        waist_value=70.0,
        waist_unit="centimeters",
        hips_value=95.0,
        hips_unit="cm",
    )
    data.normalize_measurements()

    assert data.bust_cm == 90.0
    assert data.bust_in == round(90.0 / 2.54, 1)
    assert data.waist_cm == 70.0
    assert data.waist_in == round(70.0 / 2.54, 1)
    assert data.hips_cm == 95.0
    assert data.hips_in == round(95.0 / 2.54, 1)


def test_meters_normalization():
    """Test meter measurements."""
    data = MeasurementData(
        bust_value=0.88,
        bust_unit="m",
        waist_value=0.70,
        waist_unit="meter",
        hips_value=0.96,
        hips_unit="m",
    )
    data.normalize_measurements()

    assert data.bust_cm == 88.0
    assert data.bust_in == round(0.88 * 39.3701, 1)
    assert data.waist_cm == 70.0
    assert data.waist_in == round(0.70 * 39.3701, 1)
    assert data.hips_cm == 96.0
    assert data.hips_in == round(0.96 * 39.3701, 1)


def test_mixed_units_normalization():
    """Test mixed units in a single consultation turn (cm, m, and inches)."""
    data = MeasurementData(
        bust_value=90.0,
        bust_unit="cm",
        waist_value=0.70,
        waist_unit="m",
        hips_value=36.0,
        hips_unit="inches",
    )
    data.normalize_measurements()

    # Bust from 90 cm
    assert data.bust_cm == 90.0
    assert data.bust_in == 35.4

    # Waist from 0.70 m
    assert data.waist_cm == 70.0
    assert data.waist_in == 27.6

    # Hips from 36 inches
    assert data.hips_in == 36.0
    assert data.hips_cm == 91.4


def test_partial_none_measurements():
    """Test normalization when only partial measurements or size labels are provided."""
    data = MeasurementData(
        bust_value=34.0,
        bust_unit="inches",
        usual_size="M",
    )
    data.normalize_measurements()

    assert data.bust_in == 34.0
    assert data.bust_cm == 86.4
    assert data.waist_in is None
    assert data.waist_cm is None
    assert data.hips_in is None
    assert data.hips_cm is None
    assert data.usual_size == "M"
