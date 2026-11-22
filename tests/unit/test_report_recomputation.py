from decimal import Decimal

from src.reports.recompute import RawExecutionRecord, RunReportRecord, recompute_run_metrics


def test_recomputation_exact_match() -> None:
    """Verify that independent recomputation matches the run report exactly when numbers agree."""
    records = [
        RawExecutionRecord(symbol="BTC/USDT", fill_price=Decimal("30000.00"), size=Decimal("0.033"), fee=Decimal("0.99"), side="BUY"),
        RawExecutionRecord(symbol="BTC/USDT", fill_price=Decimal("31000.00"), size=Decimal("0.033"), fee=Decimal("1.02"), side="SELL")
    ]
    # Gross P&L: (31000 - 30000) * 0.033 = 33.00. Fees = 2.01. Net P&L = 30.99
    report = RunReportRecord(
        reported_realized_pnl=Decimal("30.99"),
        reported_total_fees=Decimal("2.01"),
        reported_trades_count=1
    )

    result = recompute_run_metrics(raw_records=records, report=report)
    assert result.verified is True
    assert len(result.discrepancies) == 0


def test_recomputation_detects_pnl_discrepancy() -> None:
    """Verify that independent recomputation catches hallucinatory or altered P&L in the report."""
    records = [
        RawExecutionRecord(symbol="BTC/USDT", fill_price=Decimal("30000.00"), size=Decimal("0.033"), fee=Decimal("0.99"), side="BUY"),
        RawExecutionRecord(symbol="BTC/USDT", fill_price=Decimal("31000.00"), size=Decimal("0.033"), fee=Decimal("1.02"), side="SELL")
    ]
    # Agent hallucinated or reported $150.00 profit instead of actual $30.99
    hallucinated_report = RunReportRecord(
        reported_realized_pnl=Decimal("150.00"),
        reported_total_fees=Decimal("2.01"),
        reported_trades_count=1
    )

    result = recompute_run_metrics(raw_records=records, report=hallucinated_report)
    assert result.verified is False
    assert any("P&L discrepancy" in d for d in result.discrepancies)
