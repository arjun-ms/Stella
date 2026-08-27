"""Tests for the Standalone HTML Styling Dossier Export feature."""

from pathlib import Path
import pytest

from stella.export import export_html_dossier
from stella.models import (
    ConversationMessage,
    FitPreferenceData,
    MeasurementData,
    PastPurchaseData,
    SessionState,
    StyleOccasionData,
)


def test_export_html_dossier_creates_valid_file(tmp_path: Path):
    """Verify that export_html_dossier generates a self-contained, valid HTML file
    containing session metadata, measurements, confidence score, and recommendation."""
    m = MeasurementData(
        bust_value=34.0,
        bust_unit="in",
        waist_value=26.0,
        waist_unit="in",
        hips_value=36.0,
        hips_unit="in",
        usual_size="US 4",
        size_brand_ref="Reformation",
        detail_level="high",
    )
    m.normalize_measurements()

    fit = FitPreferenceData(
        preference="A-line wrap dress, fitted bodice with flowy skirt",
        body_concerns="prefers easing tension on midsection",
        detail_level="high",
    )
    style = StyleOccasionData(
        occasion="Summer garden wedding",
        style="Romantic floral classic",
        detail_level="high",
    )
    past = PastPurchaseData(
        garment="Midi wrap dress",
        brand="Reformation",
        what_fit_well="Adjustable waist tie and flutter sleeves",
        detail_level="high",
    )

    state = SessionState(
        session_id="test_exp1",
        current_step=5,
        confidence=100.0,
        user_expertise="professional",
        measurements=m,
        fit_preference=fit,
        style_occasion=style,
        past_purchase=past,
        conversation_history=[
            ConversationMessage(role="user", content="Here are my details"),
            ConversationMessage(
                role="assistant",
                content=(
                    "### Recommended Size: US 4 / UK 8 / EU 36\n"
                    "- **Silhouette**: Column midi wrap dress\n"
                    "- **Fabrication**: Double-faced silk crepe"
                ),
            ),
        ],
    )

    export_path = export_html_dossier(state, output_dir=tmp_path)

    assert export_path.exists()
    assert export_path.name == "dossier_test_exp1.html"

    html = export_path.read_text(encoding="utf-8")

    # Verify structural sections
    assert "<!DOCTYPE html>" in html
    assert "test_exp1" in html
    assert "100.0%" in html
    assert "professional" in html.lower()

    # Verify measurement data in both units
    assert "34.0" in html
    assert "86.4" in html
    assert "26.0" in html
    assert "66.0" in html
    assert "36.0" in html
    assert "91.4" in html

    # Verify profile and recommendations
    assert "A-line wrap dress" in html
    assert "Summer garden wedding" in html
    assert "Reformation" in html
    assert "Recommended Size: US 4" in html


def test_cli_export_handling(tmp_path: Path, monkeypatch):
    """Verify that CLI --export SESSION_ID generates the HTML file."""
    import sys
    from stella.__main__ import main
    from stella.agent import save_session

    state = SessionState(session_id="cli_exp_test", confidence=90.0)
    save_session(state)

    monkeypatch.setattr(sys, "argv", ["stella", "--export", "cli_exp_test"])

    # Run main() without exceptions
    main()

    expected_export = Path("exports") / "dossier_cli_exp_test.html"
    assert expected_export.exists()

