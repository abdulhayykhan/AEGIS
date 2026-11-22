"""AEGIS Untrusted News Intake & Prompt Injection Sanitizer.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Finding H8 & Section 5 Step 4.3)
- Book Ch. 13 (Untrusted Input Boundary & Schema Validation)
"""

import re
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class NewsSentimentItem(BaseModel):
    """Schema-validated, sanitized news sentiment payload passed onward to trade council."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    headline: str
    sentiment_score: Decimal = Field(description="Normalized sentiment score from -1.0 (bearish) to +1.0 (bullish)")
    summary: str
    risk_flag: bool
    quarantined: bool


class NewsSanitizer:
    """Isolates external news text and converts it into pure schema-validated JSON without order tools."""

    ADVERSARIAL_PATTERNS: ClassVar[list[str]] = [
        r"\b(override|system command|ignore.*instructions|withdraw|transfer|bypass)\b",
        r"\b(api[-_]?key|secret|password|bearer|token)\b",
        r"\b(drop table|select.*from|eval\(|exec\()\b"
    ]

    def sanitize_item(self, symbol: str, raw_item: dict[str, Any]) -> NewsSentimentItem:
        title = str(raw_item.get("title", "")).strip()
        summary = str(raw_item.get("summary", "")).strip()
        combined = f"{title} {summary}".lower()

        # Check for adversarial prompt injection attempts
        is_adversarial = any(bool(re.search(pat, combined)) for pat in self.ADVERSARIAL_PATTERNS)

        if is_adversarial:
            return NewsSentimentItem(
                symbol=symbol,
                headline="[QUARANTINED CONTENT]",
                sentiment_score=Decimal("0.00"),
                summary="[QUARANTINED: Prompt injection attempt detected. Input purged from model context.]",
                risk_flag=True,
                quarantined=True
            )

        # Basic sentiment scoring on trusted clean text
        bull_words = ["surge", "gain", "high", "inflow", "rally", "partnership", "growth", "approved", "etf buying"]
        bear_words = ["drop", "crash", "loss", "outflow", "fall", "hack", "investigation", "lawsuit", "ban"]

        bull_count = sum(1 for w in bull_words if w in combined)
        bear_count = sum(1 for w in bear_words if w in combined)

        score = Decimal("0.00")
        if bull_count > bear_count:
            score = Decimal("0.50")
        elif bear_count > bull_count:
            score = Decimal("-0.50")

        # Sanitize summary to safe length and remove suspicious characters
        clean_summary = re.sub(r"[^\w\s.,;:?!$%'-]", "", summary)[:280]

        return NewsSentimentItem(
            symbol=symbol,
            headline=title[:140],
            sentiment_score=score,
            summary=clean_summary,
            risk_flag=False,
            quarantined=False
        )

    def sanitize_news_batch(self, symbol: str, news_batch: list[dict[str, Any]]) -> list[NewsSentimentItem]:
        """Process batch of external news items into strictly validated items."""
        return [self.sanitize_item(symbol, item) for item in news_batch]
