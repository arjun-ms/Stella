"""Gemini API wrapper with call tracing and logging for Stella.

Provides an LLMClient that wraps the google-genai SDK, handling conversation,
structured data extraction, and recommendation generation with per-call
latency and token usage logging.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

from stella.config import get_settings
from stella.prompts import CONVERSATION_PROMPT, EXTRACTION_PROMPT, RECOMMENDATION_PROMPT


class LLMClient:
    """Wrapper around the Gemini API with tracing support."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.api_key)
        self._model = settings.model_name
        self._logs_dir = settings.logs_dir
        self._session_id: str | None = None
        self._log_path: Path | None = None

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID and configure the trace log file path."""
        self._session_id = session_id
        self._log_path = self._logs_dir / f"trace_{session_id}.jsonl"

    def _log_call(
        self,
        call_type: str,
        step: int,
        latency_ms: float,
        response: types.GenerateContentResponse,
    ) -> None:
        """Append a trace entry to the JSONL log file."""
        if self._log_path is None:
            return

        usage = response.usage_metadata
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": call_type,
            "model": self._model,
            "step": step,
            "latency_ms": round(latency_ms, 1),
            "prompt_tokens": usage.prompt_token_count if usage else None,
            "completion_tokens": usage.candidates_token_count if usage else None,
            "total_tokens": usage.total_token_count if usage else None,
        }

        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _build_contents(
        self, history: list[dict], user_message: str
    ) -> list[types.Content]:
        """Convert conversation history + new message into Gemini Content objects."""
        contents: list[types.Content] = []

        for msg in history:
            # Gemini uses "model" instead of "assistant"
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])],
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            )
        )

        return contents

    def chat(self, step: int, user_message: str, history: list[dict]) -> str:
        """Generate a conversational response from Stella.

        Args:
            step: Current consultation step (1-4).
            user_message: The instruction/context message for this turn.
            history: Prior conversation messages as {role, content} dicts.

        Returns:
            The model's text response.
        """
        contents = self._build_contents(history, user_message)

        start = time.perf_counter()
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CONVERSATION_PROMPT,
                temperature=0.7,
            ),
        )
        latency_ms = (time.perf_counter() - start) * 1000

        self._log_call("conversation", step, latency_ms, response)
        return response.text or ""

    def extract(
        self,
        step: int,
        user_answer: str,
        question_context: str,
        schema: dict,
    ) -> dict:
        """Extract structured data from a user's answer.

        Args:
            step: Current consultation step (1-4).
            user_answer: The raw user response text.
            question_context: Description of which question was asked.
            schema: JSON schema dict for the expected response format.

        Returns:
            Parsed JSON dict matching the provided schema.
        """
        prompt = (
            f"Question context: {question_context}\n\n"
            f"User's answer: {user_answer}\n\n"
            f"Extract the relevant information into the JSON schema provided."
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ]

        start = time.perf_counter()
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_PROMPT,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
        latency_ms = (time.perf_counter() - start) * 1000

        self._log_call("extraction", step, latency_ms, response)

        raw_text = response.text or "{}"
        return json.loads(raw_text)

    def recommend(self, step: int, profile_json: str) -> str:
        """Generate the final dress recommendation.

        Args:
            step: Step number (5 for recommendation).
            profile_json: JSON string of all collected profile data.

        Returns:
            The recommendation text from Stella.
        """
        prompt = (
            f"Here is the complete client profile collected during our consultation:\n\n"
            f"{profile_json}\n\n"
            f"Please provide your comprehensive size and styling recommendation."
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ]

        start = time.perf_counter()
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=RECOMMENDATION_PROMPT,
                temperature=0.6,
            ),
        )
        latency_ms = (time.perf_counter() - start) * 1000

        self._log_call("recommendation", step, latency_ms, response)
        return response.text or ""
