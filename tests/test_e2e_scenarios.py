"""End-to-End multi-scenario consultation tests across diverse customer personas.

Covers:
1. Novice wedding guest with imperial measurements (inches)
2. Professional couture buyer with metric measurements (centimeters) & high technical jargon
3. Petite silhouette outlier proportions
4. Extended plus size / curve silhouette
5. Unit omission with conversational follow-up recovery

Validates session state JSON serialization and formatted conversation transcript persistence to disk.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from stella.agent import run_consultation, save_session, save_transcript
from stella.models import SessionState


def test_e2e_scenario_1_novice_wedding_guest_inches(tmp_path: Path):
    """Scenario 1: Novice user asking for an outdoor summer wedding dress (US inches)."""
    inputs = iter([
        "Bust 34 in, waist 27 in, hips 37 in, usually wear a US 4 in Zara",
        "I love A-line or wrap dresses that aren't too tight around my stomach",
        "Summer outdoor garden wedding, romantic floral aesthetic",
        "A Reformation wrap dress in size 4 because the waist tie was adjustable",
    ])

    state = SessionState(user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            "Hi there! Could you share your bust, waist, and hips measurements?",
            "Lovely! How do you like your dresses to fit on your body?",
            "What is the occasion and style aesthetic you're looking for?",
            "Tell me about a dress you previously bought that fit you wonderfully!",
        ]
        mock_client.extract.side_effect = [
            {
                "bust_value": 34.0,
                "bust_unit": "in",
                "waist_value": 27.0,
                "waist_unit": "in",
                "hips_value": 37.0,
                "hips_unit": "in",
                "usual_size": "US 4",
                "size_brand_ref": "Zara",
                "detail_level": "high",
            },
            {
                "preference": "A-line or wrap, relaxed midsection",
                "body_concerns": "stomach area",
                "detail_level": "high",
            },
            {
                "occasion": "summer outdoor garden wedding",
                "style": "romantic floral",
                "detail_level": "high",
            },
            {
                "garment": "wrap dress",
                "brand": "Reformation",
                "size_bought": "4",
                "what_fit_well": "adjustable waist tie",
                "detail_level": "high",
            },
        ]
        mock_client.recommend.return_value = (
            "### Recommended Size: US 4 / UK 8 / EU 36\n"
            "- **Silhouette**: Soft A-line wrap dress with flutter sleeves\n"
            "- **Fabric**: Georgette or silk crepe with fluid drape"
        )
        mock_client_cls.return_value = mock_client

        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        # 1. State verification
        assert final_state.current_step == 5
        assert final_state.confidence == 100.0
        assert final_state.measurements is not None
        assert final_state.measurements.bust_in == 34.0
        assert final_state.measurements.waist_in == 27.0
        assert final_state.measurements.hips_in == 37.0
        assert final_state.measurements.bust_cm == 86.4
        assert len(final_state.conversation_history) > 0
        last_msg = final_state.conversation_history[-1].content
        assert "US 4" in last_msg

        # 2. Persistence verification (JSON & Transcript)
        json_path = save_session(final_state)
        transcript_path = save_transcript(final_state)

        assert json_path.exists()
        assert transcript_path.exists()

        json_content = json_path.read_text(encoding="utf-8")
        assert final_state.session_id in json_content
        assert '"confidence": 100.0' in json_content

        transcript_content = transcript_path.read_text(encoding="utf-8")
        assert "Reformation" in transcript_content
        assert "Summer outdoor garden wedding" in transcript_content
        assert "Recommended Size: US 4" in transcript_content


def test_e2e_scenario_2_professional_couture_metric(tmp_path: Path):
    """Scenario 2: Professional fashion buyer with metric centimeters and couture terminology."""
    inputs = iter([
        "Bust 88 cm, waist 68 cm, hips 94 cm, standard European 38 in Max Mara",
        "Structured architectural silhouettes with princess seams and bias drape, clean waist definition",
        "Charity gala black-tie event, modern minimalist aesthetic with sculptural lines",
        "Tailored wool-crepe sheath dress from Roland Mouret size UK 10 with internal bodice boning",
    ])

    state = SessionState(user_expertise="professional")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Stella question"
        mock_client.extract.side_effect = [
            {
                "bust_value": 88.0,
                "bust_unit": "cm",
                "waist_value": 68.0,
                "waist_unit": "cm",
                "hips_value": 94.0,
                "hips_unit": "cm",
                "usual_size": "EU 38",
                "size_brand_ref": "Max Mara",
                "detail_level": "high",
            },
            {
                "preference": "architectural, princess seams, bias drape",
                "body_concerns": None,
                "detail_level": "high",
            },
            {
                "occasion": "charity gala black-tie",
                "style": "modern minimalist sculptural",
                "detail_level": "high",
            },
            {
                "garment": "sheath dress",
                "brand": "Roland Mouret",
                "size_bought": "UK 10",
                "what_fit_well": "internal bodice boning, wool-crepe fabrication",
                "detail_level": "high",
            },
        ]
        mock_client.recommend.return_value = (
            "### Recommended Size: EU 38 / UK 10 / US 6\n"
            "- **Silhouette**: Column gown with architectural origami neckline and waist darting\n"
            "- **Fabrication**: Heavyweight silk gazar or double-faced crepe"
        )
        mock_client_cls.return_value = mock_client

        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        assert final_state.current_step == 5
        assert final_state.user_expertise == "professional"
        assert final_state.measurements.bust_cm == 88.0
        assert final_state.measurements.bust_in == 34.6
        assert final_state.measurements.waist_cm == 68.0
        assert final_state.measurements.waist_in == 26.8
        assert final_state.measurements.hips_cm == 94.0
        assert final_state.measurements.hips_in == 37.0

        json_path = save_session(final_state)
        transcript_path = save_transcript(final_state)

        assert json_path.exists()
        assert transcript_path.exists()
        transcript_content = transcript_path.read_text(encoding="utf-8")
        assert "Roland Mouret" in transcript_content
        assert "Charity gala" in transcript_content


def test_e2e_scenario_3_petite_outlier_proportions(tmp_path: Path):
    """Scenario 3: Petite proportions with outlier measurements (22-inch waist)."""
    inputs = iter([
        "Bust 30 inches, waist 22 inches, hips 32 inches, usually wear US 00P in Petite Studio",
        "Petite cut, prefer midi lengths that don't overwhelm a 5'1 frame",
        "Work cocktail party, elevated classic styling",
        "Aritzia slip dress in XXS with adjustable straps",
    ])

    state = SessionState(user_expertise="intermediate")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Stella question"
        mock_client.extract.side_effect = [
            {
                "bust_value": 30.0,
                "bust_unit": "in",
                "waist_value": 22.0,
                "waist_unit": "in",
                "hips_value": 32.0,
                "hips_unit": "in",
                "usual_size": "US 00P",
                "size_brand_ref": "Petite Studio",
                "detail_level": "high",
            },
            {
                "preference": "petite proportions, midi length",
                "detail_level": "high",
            },
            {
                "occasion": "work cocktail party",
                "style": "elevated classic",
                "detail_level": "high",
            },
            {
                "garment": "slip dress",
                "brand": "Aritzia",
                "size_bought": "XXS",
                "what_fit_well": "adjustable straps and torso proportion",
                "detail_level": "high",
            },
        ]
        mock_client.recommend.return_value = "Recommended Size: US 00P / UK 2 / EU 30 Petite"
        mock_client_cls.return_value = mock_client

        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        assert final_state.current_step == 5
        assert final_state.measurements.waist_in == 22.0
        assert final_state.measurements.waist_cm == 55.9

        json_path = save_session(final_state)
        assert json_path.exists()


def test_e2e_scenario_4_extended_plus_curve_silhouette(tmp_path: Path):
    """Scenario 4: Extended curve / plus size customer (US 18W / 2X)."""
    inputs = iter([
        "Bust 50 in, waist 44 in, hips 54 in, usually 2X or US 18W in Eloquii",
        "Fit and flare with empire or defined waist, supportive bust coverage and stretch fabric",
        "Anniversary dinner at an upscale restaurant, glamorous modern classic style",
        "A stretch velvet wrap dress from Universal Standard size XL that draped effortlessly",
    ])

    state = SessionState(user_expertise="intermediate")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Stella question"
        mock_client.extract.side_effect = [
            {
                "bust_value": 50.0,
                "bust_unit": "in",
                "waist_value": 44.0,
                "waist_unit": "in",
                "hips_value": 54.0,
                "hips_unit": "in",
                "usual_size": "US 18W / 2X",
                "size_brand_ref": "Eloquii",
                "detail_level": "high",
            },
            {
                "preference": "fit and flare, empire waist, supportive bust",
                "detail_level": "high",
            },
            {
                "occasion": "upscale anniversary dinner",
                "style": "glamorous modern classic",
                "detail_level": "high",
            },
            {
                "garment": "stretch velvet wrap dress",
                "brand": "Universal Standard",
                "size_bought": "XL",
                "what_fit_well": "effortless drape and stretch recovery",
                "detail_level": "high",
            },
        ]
        mock_client.recommend.return_value = "Recommended Size: US 18W / 2X / UK 22 / EU 50"
        mock_client_cls.return_value = mock_client

        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        assert final_state.current_step == 5
        assert final_state.measurements.bust_in == 50.0
        assert final_state.measurements.waist_in == 44.0
        assert final_state.measurements.hips_in == 54.0
        assert final_state.confidence == 100.0


def test_e2e_scenario_5_missing_unit_recovery_and_persistence(tmp_path: Path):
    """Scenario 5: User gives raw numbers with missing unit on turn 1, clarifies on turn 2."""
    inputs = iter([
        "36, 28, 38",       # Turn 1: unit omitted
        "inches please",    # Turn 2: clarified as inches
        "Tailored sheath with slight stretch",
        "Business cocktail networking event",
        "Banana Republic size 6 sheath dress",
    ])

    state = SessionState(user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Stella question"
        mock_client.extract.side_effect = [
            # Turn 1 (missing units)
            {"bust_value": 36.0, "waist_value": 28.0, "hips_value": 38.0, "bust_unit": None, "waist_unit": None, "hips_unit": None, "unit": None, "detail_level": "medium"},
            # Turn 2 (confirmed inches)
            {"bust_value": 36.0, "waist_value": 28.0, "hips_value": 38.0, "bust_unit": "inches", "waist_unit": "inches", "hips_unit": "inches", "unit": "inches", "detail_level": "high"},
            # Step 2
            {"preference": "tailored sheath with slight stretch", "detail_level": "high"},
            # Step 3
            {"occasion": "business cocktail", "style": "tailored", "detail_level": "high"},
            # Step 4
            {"brand": "Banana Republic", "size_bought": "6", "detail_level": "high"},
        ]
        mock_client.recommend.return_value = "Recommended Size: US 6 / UK 10 / EU 38"
        mock_client_cls.return_value = mock_client

        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        assert final_state.current_step == 5
        assert final_state.attempts_per_step[1] == 2
        assert final_state.measurements.bust_in == 36.0
        assert final_state.measurements.waist_in == 28.0
        assert final_state.measurements.hips_in == 38.0
        assert final_state.measurements.bust_cm == 91.4

        json_path = save_session(final_state)
        transcript_path = save_transcript(final_state)

        assert json_path.exists()
        assert transcript_path.exists()
        transcript_content = transcript_path.read_text(encoding="utf-8")
        assert "Banana Republic" in transcript_content
