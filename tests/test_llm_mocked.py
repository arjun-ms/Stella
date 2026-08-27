"""Integration tests for LLMClient extraction, chat, and recommendation with mocked API responses."""

from unittest.mock import MagicMock, patch
import pytest

from stella.llm import LLMClient
from stella.models import MeasurementData


@pytest.fixture
def mock_genai():
    with patch("stella.llm.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        yield mock_client


def test_llm_chat_invocation(mock_genai, tmp_path):
    with patch("stella.llm.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "fake-key"
        mock_settings.return_value.model_name = "gemini-2.5-flash"
        mock_settings.return_value.logs_dir = tmp_path

        mock_resp = MagicMock()
        mock_resp.text = "Hello! Let's talk about your measurements."
        mock_resp.usage_metadata = MagicMock(prompt_token_count=50, candidates_token_count=20, total_token_count=70)
        mock_genai.models.generate_content.return_value = mock_resp

        client = LLMClient()
        client.set_session_id("mock_session_01")
        response = client.chat(1, "Ask Q1", [])

        assert response == "Hello! Let's talk about your measurements."
        mock_genai.models.generate_content.assert_called_once()


def test_llm_chat_with_conversation_message_objects(mock_genai, tmp_path):
    """Verify that chat() accepts both raw dicts and ConversationMessage objects without TypeError."""
    from stella.models import ConversationMessage

    with patch("stella.llm.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "fake-key"
        mock_settings.return_value.model_name = "gemini-2.5-flash"
        mock_settings.return_value.logs_dir = tmp_path

        mock_resp = MagicMock()
        mock_resp.text = "Tell me about your fit preference."
        mock_resp.usage_metadata = MagicMock(prompt_token_count=60, candidates_token_count=20, total_token_count=80)
        mock_genai.models.generate_content.return_value = mock_resp

        client = LLMClient()
        client.set_session_id("mock_session_04")

        # Pass ConversationMessage objects directly
        history = [
            ConversationMessage(role="assistant", content="Welcome to Stella!"),
            ConversationMessage(role="user", content="Bust 34 in, waist 26 in, hips 36 in"),
        ]

        response = client.chat(2, "Ask fit preference", history)
        assert response == "Tell me about your fit preference."
        mock_genai.models.generate_content.assert_called_once()


def test_llm_extract_json(mock_genai, tmp_path):
    with patch("stella.llm.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "fake-key"
        mock_settings.return_value.model_name = "gemini-2.5-flash"
        mock_settings.return_value.logs_dir = tmp_path

        mock_resp = MagicMock()
        mock_resp.text = '{"bust_value": 34.0, "bust_unit": "inches", "waist_value": 26.0, "waist_unit": "inches", "hips_value": 36.0, "hips_unit": "inches", "detail_level": "high"}'
        mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=30, total_token_count=130)
        mock_genai.models.generate_content.return_value = mock_resp

        client = LLMClient()
        client.set_session_id("mock_session_02")
        schema = MeasurementData.model_json_schema()
        result = client.extract(1, "34 bust, 26 waist, 36 hips", "Q1 measurements", schema)

        assert result["bust_value"] == 34.0
        assert result["detail_level"] == "high"


def test_llm_recommend(mock_genai, tmp_path):
    with patch("stella.llm.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "fake-key"
        mock_settings.return_value.model_name = "gemini-2.5-flash"
        mock_settings.return_value.logs_dir = tmp_path

        mock_resp = MagicMock()
        mock_resp.text = "# Stella's Recommendation\n- Size: US 4 / UK 8 / EU 36\n- Silhouette: Wrap dress"
        mock_resp.usage_metadata = MagicMock(prompt_token_count=200, candidates_token_count=80, total_token_count=280)
        mock_genai.models.generate_content.return_value = mock_resp

        client = LLMClient()
        client.set_session_id("mock_session_03")
        rec = client.recommend(5, '{"confidence_score": 100.0}')

        assert "US 4 / UK 8 / EU 36" in rec
        assert "Wrap dress" in rec
