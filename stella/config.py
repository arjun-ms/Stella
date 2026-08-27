"""Configuration module for Stella.

Loads environment variables, validates application settings, and ensures
required runtime directories exist.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file at module import time
load_dotenv()


class Settings(BaseModel):
    """Application configuration settings."""

    api_key: str = Field(
        ...,
        description="Google Gemini API key loaded from GOOGLE_API_KEY environment variable",
    )
    model_name: str = Field(
        default="gemini-3.5-flash",
        description="Active Gemini model identifier to use for LLM interactions",
    )
    models: list[str] = Field(
        default_factory=lambda: ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
        description="Ordered list of fallback Gemini models to cycle through on quota exhaustion",
    )
    sessions_dir: Path = Field(
        default=Path("sessions"),
        description="Directory path for persisting conversation sessions",
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        description="Directory path for storing application and session logs",
    )


def ensure_api_key_configured(input_fn=None) -> str:
    """Ensure a Gemini API key is available, interactively prompting the user if missing."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    from stella.display import console, display_api_key_prompt
    display_api_key_prompt()

    if input_fn is not None:
        entered = input_fn().strip()
    else:
        entered = console.input("[bold cyan]🔑 Paste Gemini API Key: [/bold cyan]").strip()

    if not entered:
        raise ValueError("No API key provided. Consultation cannot start without an API key.")

    # Save to .env file automatically
    env_path = Path(".env")
    existing_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    if "GOOGLE_API_KEY=" in existing_text:
        lines = [
            f"GOOGLE_API_KEY={entered}" if line.startswith("GOOGLE_API_KEY=") else line
            for line in existing_text.splitlines()
        ]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        with env_path.open("a", encoding="utf-8") as f:
            if existing_text and not existing_text.endswith("\n"):
                f.write("\n")
            f.write(f"GOOGLE_API_KEY={entered}\n")

    os.environ["GOOGLE_API_KEY"] = entered
    get_settings.cache_clear()
    console.print("[bold green]✓ API key saved to .env successfully![/bold green]\n")
    return entered


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve the singleton Settings instance.

    Validates that GOOGLE_API_KEY or GEMINI_API_KEY is configured and creates the required
    session and log storage directories if they do not already exist.

    Returns:
        Settings: The validated application configuration instance.

    Raises:
        ValueError: If neither GOOGLE_API_KEY nor GEMINI_API_KEY is set or is empty.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "GOOGLE_API_KEY environment variable is not set. "
            "Please create a .env file (see .env.example) or export GOOGLE_API_KEY."
        )

    models_env = os.getenv("GEMINI_MODELS")
    if models_env and models_env.strip():
        models = [m.strip() for m in models_env.split(",") if m.strip()]
    else:
        single_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
        models = [single_model, "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        # Deduplicate while preserving order
        models = list(dict.fromkeys(models))

    model_name = models[0]
    sessions_dir = Path(os.getenv("STELLA_SESSIONS_DIR", "sessions"))
    logs_dir = Path(os.getenv("STELLA_LOGS_DIR", "logs"))

    settings = Settings(
        api_key=api_key.strip(),
        model_name=model_name,
        models=models,
        sessions_dir=sessions_dir,
        logs_dir=logs_dir,
    )

    # Ensure required directories exist
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    return settings

