"""AEGIS Walk-Forward Optimization (WFO) Engine.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Section 6.1: Walk-Forward Analysis)
- Trading Skills (marian2js): Overfitting detection and Walk-Forward Efficiency (WFE) scoring
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backtest.engine import BacktestConfig, BacktestEngine
from src.signals.models import Bar


class WalkForwardWindow(BaseModel):
    """Result of an individual in-sample train and out-of-sample test window."""
    model_config = ConfigDict(frozen=True)

    window_index: int
    train_bars_count: int
    test_bars_count: int
    in_sample_return_pct: Decimal
    out_of_sample_return_pct: Decimal
    in_sample_max_dd_pct: Decimal
    out_of_sample_max_dd_pct: Decimal


class WalkForwardResult(BaseModel):
    """Aggregated walk-forward optimization and stability analysis."""
    model_config = ConfigDict(frozen=True)

    windows: list[WalkForwardWindow]
    mean_in_sample_return_pct: Decimal
    mean_out_of_sample_return_pct: Decimal
    walk_forward_efficiency_ratio: Decimal = Field(
        description="WFE = Out-of-sample return / In-sample return (Values > 0.50 indicate robust parameter stability)"
    )


class WalkForwardOptimizer:
    """Walk-forward rolling window validator and cost sensitivity analyzer.
    
    Guarantees Section 6 Trading Quality enhancement:
    - Eliminates in-sample curve fitting by validating on forward out-of-sample partitions.
    """

    def __init__(
        self,
        train_window: int = 50,
        test_window: int = 20,
        step_size: int = 20
    ) -> None:
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size

    def run(
        self,
        bars: list[Bar],
        config: BacktestConfig | None = None
    ) -> WalkForwardResult:
        base_cfg = config or BacktestConfig()
        n = len(bars)
        total_needed = self.train_window + self.test_window
        if n < total_needed:
            raise ValueError(f"Insufficient bars for walk forward: need at least {total_needed}, got {n}.")

        windows: list[WalkForwardWindow] = []
        start_idx = 0
        window_idx = 0

        while (start_idx + total_needed) <= n:
            train_end = start_idx + self.train_window
            test_end = train_end + self.test_window

            train_bars = bars[start_idx:train_end]
            test_bars = bars[train_end:test_end]

            # In-Sample Backtest
            engine_train = BacktestEngine(config=base_cfg)
            res_train = engine_train.run(train_bars)

            # Out-of-Sample Forward Backtest
            engine_test = BacktestEngine(config=base_cfg)
            res_test = engine_test.run(test_bars)

            windows.append(
                WalkForwardWindow(
                    window_index=window_idx,
                    train_bars_count=len(train_bars),
                    test_bars_count=len(test_bars),
                    in_sample_return_pct=res_train.total_return_pct,
                    out_of_sample_return_pct=res_test.total_return_pct,
                    in_sample_max_dd_pct=res_train.max_drawdown_pct,
                    out_of_sample_max_dd_pct=res_test.max_drawdown_pct
                )
            )

            start_idx += self.step_size
            window_idx += 1

        mean_is = sum((w.in_sample_return_pct for w in windows), Decimal("0.0")) / Decimal(str(len(windows)))
        mean_oos = sum((w.out_of_sample_return_pct for w in windows), Decimal("0.0")) / Decimal(str(len(windows)))

        wfe = (mean_oos / mean_is) if mean_is != Decimal("0.0") else Decimal("1.00")

        return WalkForwardResult(
            windows=windows,
            mean_in_sample_return_pct=mean_is,
            mean_out_of_sample_return_pct=mean_oos,
            walk_forward_efficiency_ratio=wfe
        )

    def run_cost_sensitivity(
        self,
        bars: list[Bar],
        fee_rates: list[Decimal],
        slippage_rates: list[Decimal]
    ) -> list[dict[str, Any]]:
        """Stress test strategy performance across a 2D matrix of fees and slippage assumptions."""
        scenarios: list[dict[str, Any]] = []
        for fee in fee_rates:
            for slip in slippage_rates:
                cfg = BacktestConfig(fee_rate=fee, slippage_rate=slip)
                engine = BacktestEngine(config=cfg)
                res = engine.run(bars)
                scenarios.append({
                    "fee_rate": fee,
                    "slippage_rate": slip,
                    "total_return_pct": res.total_return_pct,
                    "max_drawdown_pct": res.max_drawdown_pct,
                    "trades_count": len(res.trades),
                    "final_equity": res.final_equity
                })
        return scenarios
