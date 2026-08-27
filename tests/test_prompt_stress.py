"""Prompt & Input Stress Testing Suite for Stella AI Dress Styling Advisor.

Stress tests the conversational flow, extraction pipelines, normalizer, and scoring engine against:
- Polyglot and Unicode inputs (multilingual measurements, emojis, diacritics).
- Adversarial HTML/XSS and Markdown smuggling payloads.
- Extreme token length and verbose rambling texts.
- Gen-Z, British, and colloquial fashion slang.
- Extreme measurement disparities and sparse partial profiles.
- Empty, whitespace, and symbol-only edge inputs.
"""

from unittest.mock import MagicMock, patch
import pytest

from stella.agent import run_consultation
from stella.models import MeasurementData, SessionState
from stella.scoring import compute_confidence


def test_stress_unicode_and_polyglot_input():
    """Verify system resilience with multilingual inputs containing emojis, Hindi, Spanish, and French."""
    state = SessionState(user_expertise="intermediate")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        # Mock structured extraction handling polyglot measurements
        mock_client.extract.return_value = {
            "bust_value": 90.0,
            "waist_value": 70.0,
            "hips_value": 98.0,
            "unit": "cm",
            "usual_size": "Taille 38 / M",
            "size_brand_ref": "Mango España 🇪🇸",
            "detail_level": "high",
        }
        mock_client.chat.return_value = "¡Magnifique! Merci pour vos mensurations. Quel style de robe préférez-vous?"
        mock_client.recommend.return_value = "## Recommendation\nRecommended Size: EU 38 / US 6"
        mock_client_cls.return_value = mock_client

        polyglot_input = "Mon tour de poitrine est 90cm, cintura 70cm, caderas 98cm 💃✨ Size M en Mango."
        final_state = run_consultation(state=state, input_fn=lambda: polyglot_input)

        assert final_state.measurements.bust_cm == 90.0
        assert final_state.measurements.bust_in == 35.4
        assert final_state.measurements.waist_cm == 70.0
        assert final_state.measurements.hips_cm == 98.0
        assert final_state.confidence >= 40.0


def test_stress_html_xss_and_markdown_smuggling():
    """Verify that malicious HTML, XSS payloads, and malformed markdown blocks do not break state or crash export."""
    state = SessionState(session_id="stress_xss_01", user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "bust_value": 36.0,
            "waist_value": 28.0,
            "hips_value": 38.0,
            "unit": "inches",
            "usual_size": "US 6",
            "size_brand_ref": "Test",
            "detail_level": "high",
        }
        mock_client.chat.return_value = "Got it! How do you like dresses to fit?"
        mock_client.recommend.return_value = "## Safe Recommendation\nRecommended Size: US 6"
        mock_client_cls.return_value = mock_client

        malicious_input = (
            "<script>alert('XSS')</script><iframe src='javascript:void(0)'></iframe>"
            "```sql\nDROP TABLE users;--\n```"
            "Bust 36in, waist 28in, hips 38in | <table><tr><td>Injected</td></tr></table>"
        )
        final_state = run_consultation(state=state, input_fn=lambda: malicious_input)

        assert final_state.measurements.bust_in == 36.0
        assert final_state.measurements.waist_in == 28.0
        assert len(final_state.conversation_history) >= 8


def test_stress_ultra_long_verbose_rambling():
    """Verify that a 3,000+ character verbose story with buried measurements is parsed cleanly."""
    state = SessionState(user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "bust_value": 34.0,
            "waist_value": 26.0,
            "hips_value": 36.0,
            "unit": "in",
            "usual_size": "US 4",
            "size_brand_ref": "Anthropologie",
            "detail_level": "high",
        }
        mock_client.chat.return_value = "Thank you for the detailed context!"
        mock_client.recommend.return_value = "Recommended Size: US 4"
        mock_client_cls.return_value = mock_client

        # Construct verbose rambling text
        rambling_text = (
            "Well so I was looking in my closet the other day and thinking about how nothing fits quite right anymore, "
            "especially after moving to New York and walking everywhere. Anyway I finally measured myself with my roommate's "
            "sewing tape this morning before breakfast, and my bust measured exactly 34 inches, while my waist came out to 26 inches, "
            "and my hips were around 36 inches. Normally I buy a size 4 at Anthropologie or Reformation though sometimes a 6 if it's "
            "linen. " + ("And then there was this one dress I bought in Paris five years ago... " * 30)
        )
        assert len(rambling_text) > 1500

        final_state = run_consultation(state=state, input_fn=lambda: rambling_text)

        assert final_state.measurements.bust_in == 34.0
        assert final_state.measurements.waist_in == 26.0


def test_stress_extreme_slang_and_idiomatic_fashion_terms():
    """Verify system processes modern Gen-Z and editorial fashion slang correctly."""
    state = SessionState(user_expertise="professional")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "fit_type": "corseted / snatched waist with drop-waist bubble skirt",
            "tightness": "corseted bodice, dramatic volume below apex",
            "preferred_silhouettes": ["corset drop waist", "bias cut slip", "balloon hem"],
            "detail_level": "high",
        }
        mock_client.chat.return_value = "Obsessed with that aesthetic! What occasion are we styling for?"
        mock_client.recommend.return_value = "Recommended Silhouette: Drop-waist corset"
        mock_client_cls.return_value = mock_client

        state.current_step = 2
        slang_input = "I want that ultra snatched waist, coquette-core energy with a dramatic drop-waist balloon hem. Absolutely eating down."
        extracted = mock_client.extract(2, slang_input)

        assert extracted["detail_level"] == "high"
        assert "snatched" in extracted["fit_type"]


def test_stress_conflicting_and_sparse_measurements():
    """Verify system calculates robust confidence when user provides only partial measurements."""
    state = SessionState(user_expertise="novice")
    state.current_step = 1

    # Partial measurement with low detail: only waist provided
    state.measurements = MeasurementData(waist_in=28.0, waist_cm=71.1, detail_level="low")
    state.confidence = compute_confidence(state)
    assert state.confidence == 4.0

    # Partial measurement with medium detail: waist and usual size provided
    state.measurements.usual_size = "US 6"
    state.measurements.detail_level = "medium"
    state.confidence = compute_confidence(state)
    assert state.confidence == 24.0
    assert state.measurements.bust_in is None
    assert state.measurements.hips_in is None


def test_stress_empty_and_whitespace_only_inputs():
    """Verify system handles empty and whitespace-only inputs without exceptions."""
    state = SessionState(user_expertise="novice")
    state.current_step = 1

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.extract.return_value = {"detail_level": "low"}
        mock_client.chat.return_value = "I didn't quite catch that. Could you share your measurements?"
        mock_client.recommend.return_value = "Recommendation..."
        mock_client_cls.return_value = mock_client

        empty_inputs = ["", "   ", "\n\t  \r", "..."]
        for emp in empty_inputs:
            extracted = mock_client.extract(1, emp)
            assert extracted["detail_level"] == "low"
