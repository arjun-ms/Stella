"""Data models for Stella - AI Size & Fit Advisor."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

UserExpertise = Literal["professional", "novice", "intermediate"]


class MeasurementData(BaseModel):
    """Extracted and normalized data from Question 1: Measurements and sizing history."""

    # Raw extracted values
    bust_value: float | None = None
    bust_unit: str | None = None  # "in", "inches", "cm", "m", etc.
    waist_value: float | None = None
    waist_unit: str | None = None
    hips_value: float | None = None
    hips_unit: str | None = None

    # Normalized values in inches
    bust_in: float | None = None
    waist_in: float | None = None
    hips_in: float | None = None

    # Normalized values in centimeters
    bust_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None

    # Primary fields for backward compatibility
    bust: float | None = None
    waist: float | None = None
    hips: float | None = None
    unit: str | None = None

    usual_size: str | None = None
    size_brand_ref: str | None = None
    detail_level: Literal["high", "medium", "low"] = "low"

    def normalize_measurements(self) -> None:
        """Convert any mixed units (m, cm, inches) into standardized inches and cm."""

        def _to_in_and_cm(val: float | None, unit_str: str | None, default_unit: str) -> tuple[float | None, float | None]:
            if val is None:
                return None, None
            u = (unit_str or default_unit or "inches").strip().lower()
            if "cm" in u or "centimeter" in u or "centimetre" in u:
                # cm to in
                cm = round(val, 1)
                inch = round(val / 2.54, 1)
                return inch, cm
            elif u in ("m", "meter", "meters", "metre", "metres") or u.startswith("meter") or u.startswith("metre"):
                # meters to cm and in
                cm = round(val * 100.0, 1)
                inch = round(val * 39.3701, 1)
                return inch, cm
            else:
                # assume inches by default
                inch = round(val, 1)
                cm = round(val * 2.54, 1)
                return inch, cm

        # Fallback if raw was passed directly into bust/waist/hips
        b_val = self.bust_value if self.bust_value is not None else self.bust
        w_val = self.waist_value if self.waist_value is not None else self.waist
        h_val = self.hips_value if self.hips_value is not None else self.hips

        b_in, b_cm = _to_in_and_cm(b_val, self.bust_unit, self.unit)
        w_in, w_cm = _to_in_and_cm(w_val, self.waist_unit, self.unit)
        h_in, h_cm = _to_in_and_cm(h_val, self.hips_unit, self.unit)

        self.bust_in = b_in
        self.bust_cm = b_cm
        self.waist_in = w_in
        self.waist_cm = w_cm
        self.hips_in = h_in
        self.hips_cm = h_cm

        # Keep primary fields updated in inches
        self.bust = b_in
        self.waist = w_in
        self.hips = h_in
        self.unit = "inches"

    def needs_unit_confirmation(self) -> bool:
        """Check if numerical measurements were provided but units were completely omitted by user."""
        has_any_num = any(
            v is not None for v in [self.bust_value, self.waist_value, self.hips_value, self.bust, self.waist, self.hips]
        )
        has_any_unit = any(
            u is not None and str(u).strip() for u in [self.bust_unit, self.waist_unit, self.hips_unit]
        )
        # If numbers are provided without unit and without brand / standard size references
        if has_any_num and not has_any_unit and not self.usual_size and not self.size_brand_ref:
            return True
        return False

    def has_out_of_bounds_measurements(self) -> tuple[bool, str]:
        """Validate if measurements are physically possible while fully supporting body diversity and outliers.

        Rejects non-positive numbers (<= 0) and extreme physically impossible values (e.g. 999 meters),
        while comfortably accepting all human body diversity (petite to extended plus sizes 8X+).

        Inclusive Outlier Thresholds:
            Bust:  14.0 in (35 cm) to 120.0 in (305 cm)
            Waist: 12.0 in (30 cm) to 120.0 in (305 cm)
            Hips:  14.0 in (35 cm) to 130.0 in (330 cm)

        Returns:
            tuple[bool, str]: (is_invalid, explanation_message)
        """
        # 1. Reject non-positive values
        for label, val in [("Bust", self.bust_in), ("Waist", self.waist_in), ("Hips", self.hips_in)]:
            if val is not None and val <= 0:
                return True, f"{label} measurement cannot be zero or negative ({val})."

        # 2. Reject physically impossible entries outside broad human ranges
        if self.bust_in is not None and (self.bust_in < 14.0 or self.bust_in > 120.0):
            return True, f"Bust measurement ({self.bust_in}\" / {self.bust_cm} cm) is outside plausible human measurements."

        if self.waist_in is not None and (self.waist_in < 12.0 or self.waist_in > 120.0):
            return True, f"Waist measurement ({self.waist_in}\" / {self.waist_cm} cm) is outside plausible human measurements."

        if self.hips_in is not None and (self.hips_in < 14.0 or self.hips_in > 130.0):
            return True, f"Hip measurement ({self.hips_in}\" / {self.hips_cm} cm) is outside plausible human measurements."

        return False, ""


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
    user_expertise: UserExpertise | None = None
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
            f"User Expertise: {self.user_expertise or 'Not selected'}",
            f"Confidence: {self.confidence:.1f}%",
            f"Created At: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Updated At: {self.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "1. Measurements (Q1):",
        ]
        if self.measurements:
            m = self.measurements
            meas_parts = []
            if m.bust_in is not None and m.bust_cm is not None:
                meas_parts.append(f"Bust: {m.bust_in} in ({m.bust_cm} cm)")
            elif m.bust is not None:
                meas_parts.append(f"Bust: {m.bust} {m.unit}")

            if m.waist_in is not None and m.waist_cm is not None:
                meas_parts.append(f"Waist: {m.waist_in} in ({m.waist_cm} cm)")
            elif m.waist is not None:
                meas_parts.append(f"Waist: {m.waist} {m.unit}")

            if m.hips_in is not None and m.hips_cm is not None:
                meas_parts.append(f"Hips: {m.hips_in} in ({m.hips_cm} cm)")
            elif m.hips is not None:
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
