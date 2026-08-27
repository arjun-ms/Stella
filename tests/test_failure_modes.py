"""TDD Suite for Failure Modes, Error Recovery, and Edge Cases in Stella."""

import json
from unittest.mock import MagicMock, patch
import pytest

from stella.agent import run_consultation
from stella.llm import LLMClient
from stella.models import MeasurementData, SessionState


def test_failure_mode_1_api_crash_graceful_recovery():
    """Behavior 1: When LLM API throws an unexpected exception during chat,
    the agent catches it, logs error, saves state, and returns state gracefully
    instead of crashing the process unhandled."""
    state = SessionState(user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        # Fail on step 1 chat
        mock_client.chat.side_effect = RuntimeError("503 Service Unavailable: High Demand")
        mock_client_cls.return_value = mock_client

        # Consultation should not raise unhandled RuntimeError
        result_state = run_consultation(state=state, input_fn=lambda: "34 bust, 26 waist")

        # Verify state was preserved at current step without crash
        assert result_state is not None
        assert result_state.current_step == 1


def test_failure_mode_2_malformed_extraction_json():
    """Behavior 2: When LLM extraction returns garbage/malformed JSON,
    extraction falls back to detail_level='low' without throwing JSONDecodeError."""
    with patch("stella.llm.genai.Client") as mock_genai_cls:
        mock_genai = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "NOT_VALID_JSON{broken"
        mock_resp.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5, total_token_count=15)
        mock_genai.models.generate_content.return_value = mock_resp
        mock_genai_cls.return_value = mock_genai

        client = LLMClient()
        schema = MeasurementData.model_json_schema()
        # Should gracefully return low-detail dict instead of crashing
        res = client.extract(1, "my size is weird", "Q1", schema)

        assert isinstance(res, dict)
        assert res.get("detail_level") == "low"


def test_failure_mode_3_consecutive_vague_answers_no_infinite_loop():
    """Behavior 3: When user gives two consecutive vague answers (attempt 1 and 2),
    agent retries once, accepts low-detail on second attempt, clamps score to low weight,
    and advances to Step 2 without looping infinitely."""
    inputs = iter([
        "idk maybe medium",       # Attempt 1 -> low detail -> triggers retry
        "still don't know sorry", # Attempt 2 -> low detail -> accepted, advances to step 2
    ])

    state = SessionState(user_expertise="novice")

    with patch("stella.agent.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Could you tell me more about your size?"
        # Both extractions return low detail
        mock_client.extract.return_value = {"detail_level": "low"}
        mock_client.recommend.return_value = "Here is your recommendation."
        mock_client_cls.return_value = mock_client

        # Run with input feeder
        final_state = run_consultation(state=state, input_fn=lambda: next(inputs, ""))

        # Verify step 1 took exactly 2 attempts
        assert final_state.attempts_per_step[1] == 2
        # Verify it accepted the low detail data and computed low confidence (40 * 0.1 = 4.0%)
        assert final_state.measurements.detail_level == "low"
        assert final_state.confidence == 4.0
        # Verify it advanced past step 1 (to step 2)
        assert final_state.current_step >= 2


def test_failure_mode_4_rate_limit_retry_notifies_user():
    """Behavior 4: When a 429 rate limit or 503 error occurs,
    _generate_with_retry displays a visible pause message with countdown info."""
    with patch("stella.llm.genai.Client") as mock_genai_cls, \
         patch("stella.display.console.print") as mock_print, \
         patch("time.sleep") as mock_sleep:

        mock_genai = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Success after retry"
        mock_resp.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5, total_token_count=15)

        # First call fails with 429 rate limit, second succeeds
        mock_genai.models.generate_content.side_effect = [
            RuntimeError("429 RESOURCE_EXHAUSTED: Please retry in 7.0s"),
            mock_resp,
        ]
        mock_genai_cls.return_value = mock_genai

        client = LLMClient()
        res = client._generate_with_retry([], MagicMock())

        assert res.text == "Success after retry"
        assert mock_sleep.called
        # Verify user was notified via console
        assert mock_print.called
        printed_text = str(mock_print.call_args)
        assert "Pausing" in printed_text or "rate limit" in printed_text.lower()


def test_failure_mode_5_model_fallback_cascade_on_quota_depletion():
    """Behavior 5: When the primary model exhausts daily quota or fails completely,
    LLMClient automatically fails over to the next model in the models cascade list."""
    with patch("stella.llm.genai.Client") as mock_genai_cls, \
         patch("stella.display.console.print") as mock_print, \
         patch("time.sleep"):

        mock_genai = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Response from fallback model"
        mock_resp.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5, total_token_count=15)

        # Primary model repeatedly returns 429 quota exhausted; secondary model succeeds
        def mock_generate(model, contents, config):
            if model == "gemini-3.5-flash":
                raise RuntimeError("429 RESOURCE_EXHAUSTED: Daily quota reached for gemini-3.5-flash")
            return mock_resp

        mock_genai.models.generate_content.side_effect = mock_generate
        mock_genai_cls.return_value = mock_genai

        client = LLMClient()
        client._models = ["gemini-3.5-flash", "gemini-2.5-flash"]
        res = client._generate_with_retry([], MagicMock(), max_retries=2)

        assert res.text == "Response from fallback model"
        assert client._current_model == "gemini-2.5-flash"
        # Verify user was notified of fallback
        assert mock_print.called
        printed_all = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Switching" in printed_all or "fallback" in printed_all.lower()


