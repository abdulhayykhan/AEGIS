from decimal import Decimal

from backtest.engine import TradeRecord
from backtest.monte_carlo import MonteCarloSimulator
from backtest.walk_forward import WalkForwardOptimizer
from src.signals.models import Bar


def generate_sample_bars(n: int = 120) -> list[Bar]:
    bars = []
    base = Decimal("30000.00")
    for i in range(n):
        # Oscillating wave with drift
        delta = Decimal((i % 20) * 100) if (i // 20) % 2 == 0 else Decimal((20 - (i % 20)) * 100)
        p = base + delta + Decimal(i * 10)
        bars.append(
            Bar(
                ts=1700000000 + (i * 86400),
                open=p - Decimal(20),
                high=p + Decimal(150),
                low=p - Decimal(150),
                close=p,
                volume=Decimal("10000.0")
            )
        )
    return bars


def test_walk_forward_splits_and_optimization() -> None:
    bars = generate_sample_bars(120)
    optimizer = WalkForwardOptimizer(
        train_window=50,
        test_window=20,
        step_size=20
    )
    result = optimizer.run(bars)
    assert len(result.windows) >= 2
    for w in result.windows:
        assert w.train_bars_count == 50
        assert w.test_bars_count == 20
        assert w.in_sample_return_pct is not None
        assert w.out_of_sample_return_pct is not None
    assert result.mean_out_of_sample_return_pct is not None


def test_monte_carlo_drawdown_distribution() -> None:
    # 20 simulated trades
    trades = [
        TradeRecord(
            entry_ts=1700000000 + (i * 86400),
            exit_ts=1700000000 + ((i + 1) * 86400),
            entry_price=Decimal("30000.00"),
            exit_price=Decimal("30500.00") if i % 3 != 0 else Decimal("29200.00"),
            units=Decimal("0.03"),
            pnl=Decimal("15.00") if i % 3 != 0 else Decimal("-24.00"),
            fee_paid=Decimal("0.90"),
            slippage_loss=Decimal("0.45"),
            exit_reason="TP" if i % 3 != 0 else "SL"
        )
        for i in range(20)
    ]
    mc = MonteCarloSimulator(num_simulations=200, initial_capital=Decimal("10000.00"))
    mc_result = mc.run(trades)
    assert mc_result.num_simulations == 200
    assert mc_result.max_drawdown_p95 >= Decimal("0.00")
    assert mc_result.ruin_probability >= Decimal("0.00")
    assert mc_result.mean_final_equity > Decimal("0.00")


def test_cost_sensitivity_analysis() -> None:
    bars = generate_sample_bars(90)
    optimizer = WalkForwardOptimizer()
    sensitivity = optimizer.run_cost_sensitivity(
        bars=bars,
        fee_rates=[Decimal("0.0005"), Decimal("0.0010"), Decimal("0.0020")],
        slippage_rates=[Decimal("0.0002"), Decimal("0.0005"), Decimal("0.0010")]
    )
    assert len(sensitivity) == 9
    for scenario in sensitivity:
        assert "fee_rate" in scenario
        assert "slippage_rate" in scenario
        assert "total_return_pct" in scenario
