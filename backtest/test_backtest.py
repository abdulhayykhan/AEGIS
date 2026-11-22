from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backtest.engine import BacktestConfig, BacktestEngine
from backtest.report import generate_backtest_report
from src.signals.models import Bar


def generate_sample_bars(n: int = 100, trend: str = "up") -> list[Bar]:
    """Generate synthetic bars for testing."""
    bars: list[Bar] = []
    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    price = Decimal("100.0")

    for i in range(n):
        if trend == "up":
            price += Decimal("1.5")
        elif trend == "down":
            price -= Decimal("1.5")
        else:
            price += Decimal("0.5") if i % 2 == 0 else -Decimal("0.5")

        high = price + Decimal("2.0")
        low = price - Decimal("2.0")
        bar = Bar(
            ts=int((base_time + timedelta(days=i)).timestamp()),
            open=price,
            high=high,
            low=low,
            close=price,
            volume=Decimal("10000.0")
        )
        bars.append(bar)
    return bars


def test_backtest_strictly_prohibits_lookahead() -> None:
    """Verify that decisions at bar T use only bars up to T."""
    bars = generate_sample_bars(n=60, trend="up")
    config = BacktestConfig(
        initial_capital=Decimal("10000.0"),
        fee_rate=Decimal("0.001"),       # 0.1% fee
        slippage_rate=Decimal("0.0005")   # 0.05% slippage
    )
    engine = BacktestEngine(config=config)

    # In engine run, record the highest bar timestamp available at each decision point
    result = engine.run(bars)
    for decision in result.decision_history:
        assert decision.decision_bar_ts <= decision.current_bar_ts, (
            f"Lookahead detected: decision used bar ts {decision.decision_bar_ts} "
            f"which is beyond current bar {decision.current_bar_ts}"
        )


def test_backtest_deducts_fees_and_slippage() -> None:
    """Verify that realistic pessimistic fees and slippage are deducted from every fill."""
    bars = generate_sample_bars(n=60, trend="up")
    config = BacktestConfig(
        initial_capital=Decimal("10000.0"),
        fee_rate=Decimal("0.001"),       # 0.1%
        slippage_rate=Decimal("0.0005")   # 0.05%
    )
    engine = BacktestEngine(config=config)
    result = engine.run(bars)

    if len(result.trades) > 0:
        total_fees = sum(t.fee_paid for t in result.trades)
        total_slippage = sum(t.slippage_loss for t in result.trades)
        assert total_fees > Decimal(0), "Fees must be strictly deducted"
        assert total_slippage > Decimal(0), "Slippage must be accounted for"


def test_backtest_report_compares_with_benchmark() -> None:

    """Verify honest report contains both strategy metrics and buy-and-hold benchmark."""
    bars = generate_sample_bars(n=80, trend="up")
    config = BacktestConfig(
        initial_capital=Decimal("10000.0"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005")
    )
    engine = BacktestEngine(config=config)
    result = engine.run(bars)

    report_md = generate_backtest_report(result)
    assert "Benchmark (Buy & Hold)" in report_md
    assert "Strategy Return" in report_md
    assert "Max Drawdown" in report_md
    assert "Total Trades" in report_md
    assert "Total Fees & Slippage" in report_md
