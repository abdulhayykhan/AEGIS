from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backtest.engine import BacktestConfig, BacktestEngine
from backtest.report import generate_backtest_report
from src.signals.models import Bar


def generate_multi_regime_dataset(num_bars: int = 600) -> list[Bar]:
    """Generate a multi-regime market dataset over 600 daily bars:
    - Phase 1 (Bars 0-200): Warmup base building around 25,000 - 30,000 USDT
    - Phase 2 (Bars 201-400): Strong Bull Market (30,000 -> 55,000 USDT)
    - Phase 3 (Bars 401-480): Distribution & Consolidation (55,000 -> 50,000 USDT)
    - Phase 4 (Bars 481-600): Bear Market Drawdown (50,000 -> 28,000 USDT)
    """
    bars: list[Bar] = []
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    current_price = Decimal("26000.00")

    for i in range(num_bars):
        if i <= 200:
            # Base accumulation: oscillating drift
            delta = Decimal("25.0") if i % 2 == 0 else -Decimal("20.0")
        elif i <= 400:
            # Strong bull trend
            delta = Decimal("140.0") + (Decimal("50.0") if i % 3 == 0 else -Decimal("30.0"))
        elif i <= 480:
            # Choppy distribution
            delta = Decimal("60.0") if i % 2 == 0 else -Decimal("90.0")
        else:
            # Bear drawdown
            delta = -Decimal("160.0") + (Decimal("30.0") if i % 4 == 0 else -Decimal("40.0"))

        current_price = max(Decimal("1000.0"), current_price + delta)
        high = current_price + Decimal("350.0")
        low = current_price - Decimal("350.0")
        
        bars.append(
            Bar(
                ts=int((base_time + timedelta(days=i)).timestamp()),
                open=current_price - (delta / Decimal(2)),
                high=high,
                low=low,
                close=current_price,
                volume=Decimal("1250000.00")
            )
        )
    return bars



def main() -> None:
    bars = generate_multi_regime_dataset(num_bars=600)
    config = BacktestConfig(

        initial_capital=Decimal("10000.00"),
        fee_rate=Decimal("0.001"),       # 0.10% taker fee
        slippage_rate=Decimal("0.0005"),  # 0.05% fill slippage
        fast_period=50,
        slow_period=200,
        atr_period=14
    )
    engine = BacktestEngine(config=config)
    result = engine.run(bars)

    report_content = generate_backtest_report(result)
    output_path = Path("docs/backtest-report.md")
    output_path.write_text(report_content, encoding="utf-8")
    print(f"Backtest successfully executed! Report saved to {output_path}")


if __name__ == "__main__":
    main()
