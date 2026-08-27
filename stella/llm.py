"""Gemini API wrapper with call tracing, logging, and rate-limit backoff for Stella.

Provides an LLMClient that wraps the google-genai SDK, handling conversation,
structured data extraction, and recommendation generation with per-call
latency, token usage logging, and resilient exponential backoff on 429 quota limits.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from google import genai
from google.genai import types

from stella.config import get_settings
from stella.prompts import CONVERSATION_PROMPT, EXTRACTION_PROMPT, RECOMMENDATION_PROMPT


class LLMClient:
    """Wrapper around the Gemini API with tracing and rate-limit backoff support."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.api_key)
        self._models: list[str] = list(settings.models)
        self._model_idx: int = 0
        self._logs_dir = settings.logs_dir
        self._session_id: str | None = None
        self._log_path: Path | None = None
        self._on_status: Callable[[str, str], None] | None = None

    def set_status_callback(self, callback: Callable[[str, str], None] | None) -> None:
        """Set a callback to receive status events ('rate_limit', 'model_switch', 'error')."""
        self._on_status = callback

    @property
    def _current_model(self) -> str:
        """Get the currently active model from the models cascade list."""
        if 0 <= self._model_idx < len(self._models):
            return self._models[self._model_idx]
        return self._models[0] if self._models else "gemini-3.5-flash"

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
            "model": self._current_model,
            "step": step,
            "latency_ms": round(latency_ms, 1),
            "prompt_tokens": usage.prompt_token_count if usage else None,
            "completion_tokens": usage.candidates_token_count if usage else None,
            "total_tokens": usage.total_token_count if usage else None,
        }

        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _generate_with_retry(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
        max_retries: int = 6,
    ) -> types.GenerateContentResponse:
        """Call Gemini API with automatic exponential backoff on 429 quota limits or 503 transient errors,
        failing over to the next model in the cascade list if daily quota is exhausted."""
        attempt = 0
        while True:
            try:
                return self._client.models.generate_content(
                    model=self._current_model,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                err_msg = str(e)
                attempt += 1
                is_rate_limit = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg
                is_transient = "503" in err_msg or "UNAVAILABLE" in err_msg or "500" in err_msg or "502" in err_msg or "high demand" in err_msg
                is_daily_or_deprecated = (
                    "daily" in err_msg.lower()
                    or "limit: 0" in err_msg.lower()
                    or "404" in err_msg
                    or "not found" in err_msg.lower()
                    or attempt > max_retries
                )

                from stella.display import console

                # If daily limit reached or retry cap reached, check if we have a fallback model in cascade
                if is_daily_or_deprecated and self._model_idx + 1 < len(self._models):
                    old_model = self._current_model
                    self._model_idx += 1
                    new_model = self._current_model
                    switch_msg = f"Model '{old_model}' quota exhausted. Switching to fallback model '{new_model}'..."
                    console.print(f"\n[cyan]🔄 {switch_msg}[/cyan]")
                    if self._on_status:
                        self._on_status("model_switch", switch_msg)
                    attempt = 0
                    continue

                if (is_rate_limit or is_transient) and attempt <= max_retries:
                    # Extract suggested delay if present (e.g. 'retry in 7.5s')
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                    if match:
                        sleep_s = float(match.group(1)) + 1.5
                    elif is_rate_limit:
                        sleep_s = 7.0 * (1.4 ** (attempt - 1))
                    else:
                        sleep_s = 4.0 * (1.5 ** (attempt - 1))

                    reason = "API rate limit reached" if is_rate_limit else "Server traffic spike"
                    retry_msg = f"{reason}. Pausing {int(sleep_s)}s before automatic retry... (Attempt {attempt}/{max_retries})"
                    console.print(f"[yellow]⏳ {retry_msg}[/yellow]")
                    if self._on_status:
                        self._on_status("rate_limit", retry_msg)
                    time.sleep(sleep_s)
                else:
                    if self._on_status:
                        self._on_status("error", str(e))
                    raise

    def _build_contents(
        self, history: list[dict], user_message: str
    ) -> list[types.Content]:
        """Convert conversation history + new message into Gemini Content objects."""
        contents: list[types.Content] = []

        for msg in history:
            msg_role = msg.role if hasattr(msg, "role") else msg.get("role", "user")
            msg_content = msg.content if hasattr(msg, "content") else msg.get("content", "")

            # Gemini uses "model" instead of "assistant"
            role = "model" if msg_role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg_content)],
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
        """Generate a conversational response from Stella."""
        contents = self._build_contents(history, user_message)
        config = types.GenerateContentConfig(
            system_instruction=CONVERSATION_PROMPT,
            temperature=0.7,
        )

        start = time.perf_counter()
        response = self._generate_with_retry(contents, config)
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
        """Extract structured data from a user's answer."""
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
        config = types.GenerateContentConfig(
            system_instruction=EXTRACTION_PROMPT,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.1,
        )

        start = time.perf_counter()
        response = self._generate_with_retry(contents, config)
        latency_ms = (time.perf_counter() - start) * 1000

        self._log_call("extraction", step, latency_ms, response)

        raw_text = response.text or "{}"
        try:
            return json.loads(raw_text)
        except Exception:
            return {"detail_level": "low"}

    def recommend(self, step: int, profile_json: str) -> str:
        """Generate the final dress recommendation."""
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
        config = types.GenerateContentConfig(
            system_instruction=RECOMMENDATION_PROMPT,
            temperature=0.6,
        )

        start = time.perf_counter()
        response = self._generate_with_retry(contents, config)
        latency_ms = (time.perf_counter() - start) * 1000

        self._log_call("recommendation", step, latency_ms, response)
        return response.text or ""
