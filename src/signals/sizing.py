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


def calculate_volatility_targeted_size(
    equity: Decimal,
    entry_price: Decimal,
    current_atr: Decimal,
    target_vol_pct: Decimal = Decimal("0.15"),
    annual_days: int = 365,
    min_size: Decimal = Decimal("0.001"),
    step_size: Decimal = Decimal("0.001"),
    max_position_pct: Decimal = Decimal("0.10")
) -> SizingResult:
    """Volatility-targeted position sizing scaling inversely with instrument volatility.
    
    Target Annual Volatility = Target Portfolio Vol / sqrt(365).
    Units = (equity * daily_target_vol) / daily_atr.
    """
    if equity <= Decimal(0) or entry_price <= Decimal(0) or current_atr <= Decimal(0):
        raise ValueError("Equity, entry price, and ATR must be strictly positive.")

    # Daily target volatility budget
    daily_target_vol = target_vol_pct / Decimal(str(annual_days ** 0.5))
    target_dollar_vol = equity * daily_target_vol
    raw_units = target_dollar_vol / current_atr

    # Enforce 10% instrument notional cap
    max_units_cap = (equity * max_position_pct) / entry_price
    chosen_units = min(raw_units, max_units_cap)

    # Step size rounding
    steps = (chosen_units / step_size).to_integral_value(rounding=ROUND_DOWN)
    final_units = steps * step_size
    if final_units < min_size:
        final_units = Decimal(0)

    stop_distance = Decimal("2.0") * current_atr
    notional = final_units * entry_price
    risk_amount = final_units * stop_distance

    return SizingResult(
        units=final_units,
        notional_value=notional,
        risk_amount=risk_amount,
        stop_distance=stop_distance
    )


def apply_correlation_penalty(
    raw_size: Decimal,
    symbol: str,
    open_positions: list[str],
    correlation_matrix: dict[str, dict[str, Decimal]] | None = None
) -> Decimal:
    """Apply portfolio concentration discount if adding an instrument correlated with existing open positions."""
    if not open_positions or raw_size <= Decimal(0):
        return raw_size

    default_matrix = {
        "BTC/USDT": {"ETH/USDT": Decimal("0.85"), "SOL/USDT": Decimal("0.70")},
        "ETH/USDT": {"BTC/USDT": Decimal("0.85"), "SOL/USDT": Decimal("0.75")},
        "SOL/USDT": {"BTC/USDT": Decimal("0.70"), "ETH/USDT": Decimal("0.75")}
    }
    matrix = correlation_matrix or default_matrix
    sym_corrs = matrix.get(symbol, {})

    max_corr = Decimal("0.00")
    for pos_sym in open_positions:
        if pos_sym != symbol:
            corr = sym_corrs.get(pos_sym, Decimal("0.00"))
            max_corr = max(max_corr, corr)

    # Penalty formula: If correlation > 0.70, haircut size by (corr - 0.70) * 1.5
    if max_corr > Decimal("0.70"):
        penalty_factor = Decimal("1.0") - ((max_corr - Decimal("0.70")) * Decimal("1.5"))
        penalty_factor = max(Decimal("0.50"), penalty_factor)
        return (raw_size * penalty_factor).quantize(Decimal("0.001"), rounding=ROUND_DOWN)

    return raw_size


def check_spread_and_slippage_guard(
    limit_price: Decimal,
    mark_price: Decimal,
    max_allowed_spread_pct: Decimal = Decimal("0.01")  # 1% max spread guard
) -> tuple[bool, str]:
    """Spread and slippage guard checking limit price deviation from mark price."""
    if mark_price <= Decimal(0):
        return False, "Invalid mark price: must be positive."

    deviation = abs(limit_price - mark_price) / mark_price
    if deviation > max_allowed_spread_pct:
        return (
            False,
            (
                f"Spread/slippage breach: order price {limit_price:.2f} deviates {deviation * Decimal(100):.2f}% "
                f"from mark price {mark_price:.2f}, which exceeds maximum allowed {max_allowed_spread_pct * Decimal(100):.2f}%."
            )
        )
    return True, "Spread within acceptable guard limits."
