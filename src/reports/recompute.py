from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RawExecutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    fill_price: Decimal
    size: Decimal
    fee: Decimal
    side: str  # "BUY" or "SELL"


class RunReportRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    reported_realized_pnl: Decimal
    reported_total_fees: Decimal
    reported_trades_count: int


class RecomputeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified: bool
    recomputed_pnl: Decimal
    recomputed_fees: Decimal
    discrepancies: list[str]


def recompute_run_metrics(raw_records: list[RawExecutionRecord], report: RunReportRecord) -> RecomputeResult:
    """Independent mathematical recomputation of headline metrics from source execution records.
    
    Guarantees the review contract from PRD Section 14:
    - Never trusts reported numbers without source table verification.
    """
    discrepancies: list[str] = []

    # Separate buys and sells
    buys = [r for r in raw_records if r.side == "BUY"]
    sells = [r for r in raw_records if r.side == "SELL"]

    total_fees = sum((r.fee for r in raw_records), Decimal("0.00"))

    # Compute realized PnL across matching pairs
    realized_pnl = Decimal("0.00")
    for buy, sell in zip(buys, sells):
        units = min(buy.size, sell.size)
        gross_pnl = (sell.fill_price - buy.fill_price) * units
        realized_pnl += gross_pnl

    net_realized_pnl = realized_pnl - total_fees

    # 1. Verify Net P&L
    if abs(net_realized_pnl - report.reported_realized_pnl) > Decimal("0.01"):
        discrepancies.append(
            f"P&L discrepancy: Recomputed={net_realized_pnl:.2f} USDT vs Reported={report.reported_realized_pnl:.2f} USDT"
        )

    # 2. Verify Fees
    if abs(total_fees - report.reported_total_fees) > Decimal("0.01"):
        discrepancies.append(
            f"Fee discrepancy: Recomputed={total_fees:.2f} USDT vs Reported={report.reported_total_fees:.2f} USDT"
        )

    return RecomputeResult(
        verified=len(discrepancies) == 0,
        recomputed_pnl=net_realized_pnl,
        recomputed_fees=total_fees,
        discrepancies=discrepancies
    )
