from decimal import ROUND_DOWN, Decimal

from src.signals.models import SizingResult


def calculate_position_size(
    equity: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
    min_size: Decimal = Decimal("0.001"),
    step_size: Decimal = Decimal("0.001"),
    max_risk_pct: Decimal = Decimal("0.01"),      # 1% default
    max_position_pct: Decimal = Decimal("0.10")  # 10% default
) -> SizingResult:
    """Calculate deterministic position size according to Section 7 & 11.
    
    1. Computes risk budget: equity * max_risk_pct
    2. Computes stop distance: entry_price - stop_loss
    3. Derives raw units: risk_budget / stop_distance
    4. Applies 10% instrument equity cap: (equity * max_position_pct) / entry_price
    5. Normalizes units down to step_size.
    """
    if stop_loss >= entry_price:
        raise ValueError("Stop loss must be strictly below entry price for long orders.")

    if equity <= Decimal(0) or entry_price <= Decimal(0):
        raise ValueError("Equity and entry price must be strictly positive.")

    stop_distance = entry_price - stop_loss

    # 1% per-trade risk budget
    risk_budget = equity * max_risk_pct
    raw_units = risk_budget / stop_distance

    # 10% max instrument allocation cap
    max_capital = equity * max_position_pct
    max_units_cap = max_capital / entry_price

    chosen_units = min(raw_units, max_units_cap)

    # Truncate / round down to step_size
    steps = (chosen_units / step_size).to_integral_value(rounding=ROUND_DOWN)
    final_units = steps * step_size

    if final_units < min_size:
        final_units = Decimal(0)

    notional_value = final_units * entry_price
    risk_amount = final_units * stop_distance

    return SizingResult(
        units=final_units,
        notional_value=notional_value,
        risk_amount=risk_amount,
        stop_distance=stop_distance
    )
