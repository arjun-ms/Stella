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
        default="gemini-2.5-flash",
        description="Gemini model identifier to use for LLM interactions",
    )
    sessions_dir: Path = Field(
        default=Path("sessions"),
        description="Directory path for persisting conversation sessions",
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        description="Directory path for storing application and session logs",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve the singleton Settings instance.

    Validates that GOOGLE_API_KEY is configured and creates the required
    session and log storage directories if they do not already exist.

    Returns:
        Settings: The validated application configuration instance.

    Raises:
        ValueError: If GOOGLE_API_KEY is not set or is empty.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "GOOGLE_API_KEY environment variable is not set. "
            "Please create a .env file (see .env.example) or export GOOGLE_API_KEY."
        )

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    sessions_dir = Path(os.getenv("STELLA_SESSIONS_DIR", "sessions"))
    logs_dir = Path(os.getenv("STELLA_LOGS_DIR", "logs"))

    settings = Settings(
        api_key=api_key.strip(),
        model_name=model_name,
        sessions_dir=sessions_dir,
        logs_dir=logs_dir,
    )

    # Ensure required directories exist
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    return settings
