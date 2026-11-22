import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    MARKET = "MARKET"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: uuid.UUID = Field(description="Unique proposal identifier")
    idempotency_key: uuid.UUID = Field(description="Unique idempotency key per order")
    symbol: str = Field(description="Instrument trading pair (e.g. BTC/USDT)")
    side: OrderSide = Field(description="Order side: BUY or SELL")
    order_type: OrderType = Field(description="Order type: LIMIT or STOP_LOSS_LIMIT")
    price: Decimal = Field(gt=Decimal(0), description="Limit price in quote currency")
    size: Decimal = Field(gt=Decimal(0), description="Order size in base currency")
    stop_loss: Decimal = Field(gt=Decimal(0), description="Mandatory stop loss price")
    take_profit: Decimal | None = Field(default=None, description="Optional target exit price")
    rationale_id: str = Field(description="Auditable strategy rationale reference ID")


class GateContext(BaseModel):
    account_equity: Decimal
    peak_equity: Decimal
    daily_realized_loss: Decimal
    open_positions: dict[str, Decimal]
    open_position_notionals: dict[str, Decimal]
    orders_today_count: int
    allowed_instruments: set[str]
    last_price: Decimal
    last_bar_ts: datetime
    current_ts: datetime
    bar_interval: timedelta
    kill_switch_active: bool
    used_idempotency_keys: set[uuid.UUID]
    mode: str = "PAPER"


class GateDecisionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    checks: dict[str, bool]
    reasons: list[str]
    decided_at: datetime
