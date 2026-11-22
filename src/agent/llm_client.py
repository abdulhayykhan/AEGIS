"""AEGIS LLM Provider Client with Token Accounting & Cost Enforcement.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Finding H1 & Section 5 Step 4)
- PRD Section 10: Model Harness & Turn/Cost Limits
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LLMDecisionResponse(BaseModel):
    """Structured decision output from LLM model harness with token accounting."""
    model_config = ConfigDict(frozen=True)

    recommendation: str  # "BUY", "SELL", "HOLD"
    conviction: Decimal = Field(default=Decimal("0.75"), description="Conviction score between 0.00 and 1.00")
    thesis: str = Field(description="Mathematical and indicator reasoning")
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class BaseLLMClient(ABC):
    """Abstract base interface for LLM deliberation in the AEGIS loop."""

    # Default rates: Claude 3.5 Sonnet ($3.00/M input, $15.00/M output)
    INPUT_COST_PER_MILLION: Decimal = Decimal("3.00")
    OUTPUT_COST_PER_MILLION: Decimal = Decimal("15.00")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate real monetary cost in USD for token consumption."""
        in_cost = (Decimal(input_tokens) / Decimal("1000000.0")) * self.INPUT_COST_PER_MILLION
        out_cost = (Decimal(output_tokens) / Decimal("1000000.0")) * self.OUTPUT_COST_PER_MILLION
        return round(in_cost + out_cost, 6)

    @abstractmethod
    def generate_trade_decision(
        self,
        symbol: str,
        system_prompt: str,
        user_prompt: str,
        available_skills: list[str]
    ) -> LLMDecisionResponse:
        """Generate trade decision rationale with real token counting."""


class MockLLMClient(BaseLLMClient):
    """High-fidelity offline LLM simulator providing verifiable token accounting."""

    def generate_trade_decision(
        self,
        symbol: str,
        system_prompt: str,
        user_prompt: str,
        available_skills: list[str]
    ) -> LLMDecisionResponse:
        # Approximate tokens based on prompt character length (~4 chars per token)
        input_tokens = max(100, len(system_prompt + user_prompt + " ".join(available_skills)) // 4)
        output_tokens = 65

        # Extract bias from user prompt
        text = user_prompt.lower()
        if "bull" in text or "uptrend" in text:
            rec = "BUY"
            conv = Decimal("0.85")
            thesis = f"Strong trend-following alignment on {symbol}; moving averages confirming expansion."
        elif "bear" in text or "downtrend" in text:
            rec = "SELL"
            conv = Decimal("0.80")
            thesis = f"Bearish divergence on {symbol}; risk-reducing exits indicated."
        else:
            rec = "HOLD"
            conv = Decimal("0.50")
            thesis = f"Consolidation range detected on {symbol}; preserving capital."

        cost = self.calculate_cost(input_tokens, output_tokens)
        return LLMDecisionResponse(
            recommendation=rec,
            conviction=conv,
            thesis=thesis,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost
        )
