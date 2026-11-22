from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    ts: int = Field(description="Unix timestamp in seconds (UTC)")
    open: Decimal = Field(description="Open price")
    high: Decimal = Field(description="High price")
    low: Decimal = Field(description="Low price")
    close: Decimal = Field(description="Close price")
    volume: Decimal = Field(description="Volume traded")


class SizingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    units: Decimal = Field(description="Final position size in instrument base units")
    notional_value: Decimal = Field(description="Total position value at entry price")
    risk_amount: Decimal = Field(description="Monetary amount risked to stop loss")
    stop_distance: Decimal = Field(description="Distance from entry to stop loss")

