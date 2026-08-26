"""Data models for Stella - AI Size & Fit Advisor."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class MeasurementData(BaseModel):
    """Extracted data from Question 1: Measurements and sizing history."""

    bust: float | None = None
    waist: float | None = None
    hips: float | None = None
    unit: str = "inches"
    usual_size: str | None = None
    size_brand_ref: str | None = None
    detail_level: Literal["high", "medium", "low"] = "low"


class FitPreferenceData(BaseModel):
    """Extracted data from Question 2: Fit preferences and body silhouette."""

    preference: str | None = None
    body_concerns: str | None = None
    detail_level: Literal["high", "medium", "low"] = "low"


class StyleOccasionData(BaseModel):
    """Extracted data from Question 3: Event occasion and aesthetic style."""

    occasion: str | None = None
    style: str | None = None
    detail_level: Literal["high", "medium", "low"] = "low"


class PastPurchaseData(BaseModel):
    """Extracted data from Question 4: Past garment purchases and what fit well."""

    garment: str | None = None
    brand: str | None = None
    what_fit_well: str | None = None
    detail_level: Literal["high", "medium", "low"] = "low"


class ConversationMessage(BaseModel):
    """Single message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    """Full conversational session state for Stella."""

    session_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    current_step: int = 0
    confidence: float = 0.0
    measurements: MeasurementData | None = None
    fit_preference: FitPreferenceData | None = None
    style_occasion: StyleOccasionData | None = None
    past_purchase: PastPurchaseData | None = None
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    attempts_per_step: dict[int, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_message(self, role: Literal["user", "assistant"], content: str) -> None:
        """Append a message to conversation history and update timestamp."""
        self.conversation_history.append(ConversationMessage(role=role, content=content))
        self.updated_at = datetime.now()

    def get_transcript(self) -> str:
        """Return a formatted string of the conversation history."""
        if not self.conversation_history:
            return "No conversation history recorded."
        lines: list[str] = []
        for msg in self.conversation_history:
            role_label = "Stella" if msg.role == "assistant" else "User"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)

    def state_dump(self) -> str:
        """Return a pretty-printed summary of all extracted data and confidence."""
        sections = [
            f"=== Session State [{self.session_id}] ===",
            f"Current Step: {self.current_step}/5",
            f"Confidence: {self.confidence:.1f}%",
            f"Created At: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Updated At: {self.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "1. Measurements (Q1):",
        ]
        if self.measurements:
            m = self.measurements
            meas_parts = []
            if m.bust is not None:
                meas_parts.append(f"Bust: {m.bust} {m.unit}")
            if m.waist is not None:
                meas_parts.append(f"Waist: {m.waist} {m.unit}")
            if m.hips is not None:
                meas_parts.append(f"Hips: {m.hips} {m.unit}")
            meas_summary = ", ".join(meas_parts) if meas_parts else "None specified"
            sections.append(f"  - Body: {meas_summary}")
            sections.append(f"  - Usual Size: {m.usual_size or 'N/A'} (Brand Ref: {m.size_brand_ref or 'N/A'})")
            sections.append(f"  - Detail Level: {m.detail_level}")
        else:
            sections.append("  (Not yet collected)")

        sections.append("\n2. Fit Preference (Q2):")
        if self.fit_preference:
            fp = self.fit_preference
            sections.append(f"  - Preference: {fp.preference or 'N/A'}")
            sections.append(f"  - Body Concerns: {fp.body_concerns or 'N/A'}")
            sections.append(f"  - Detail Level: {fp.detail_level}")
        else:
            sections.append("  (Not yet collected)")

        sections.append("\n3. Style & Occasion (Q3):")
        if self.style_occasion:
            so = self.style_occasion
            sections.append(f"  - Occasion: {so.occasion or 'N/A'}")
            sections.append(f"  - Style: {so.style or 'N/A'}")
            sections.append(f"  - Detail Level: {so.detail_level}")
        else:
            sections.append("  (Not yet collected)")

        sections.append("\n4. Past Purchase (Q4):")
        if self.past_purchase:
            pp = self.past_purchase
            sections.append(f"  - Garment: {pp.garment or 'N/A'}")
            sections.append(f"  - Brand: {pp.brand or 'N/A'}")
            sections.append(f"  - What Fit Well: {pp.what_fit_well or 'N/A'}")
            sections.append(f"  - Detail Level: {pp.detail_level}")
        else:
            sections.append("  (Not yet collected)")

        sections.append(f"\nTotal Messages: {len(self.conversation_history)}")
        sections.append(f"Attempts Per Step: {self.attempts_per_step}")

        return "\n".join(sections)
