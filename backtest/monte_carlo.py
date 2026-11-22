"""AEGIS Monte Carlo Sequence Permutation & Ruin Probability Simulator.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Section 6.1: Monte Carlo Resampling & Drawdown Confidence)
- TradingSkills / Claude Trading Skills: Resampling trade series for tail-risk estimation
"""

import random
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backtest.engine import TradeRecord


class MonteCarloResult(BaseModel):
    """Statistical distribution of trading performance under trade order reshuffling."""
    model_config = ConfigDict(frozen=True)

    num_simulations: int
    mean_final_equity: Decimal
    median_final_equity: Decimal
    p05_final_equity: Decimal = Field(description="5th percentile conservative final equity")
    max_drawdown_mean: Decimal
    max_drawdown_p95: Decimal = Field(description="95th percentile maximum drawdown")
    max_drawdown_p99: Decimal = Field(description="99th percentile maximum drawdown")
    ruin_probability: Decimal = Field(description="Probability of equity breaching severe ruin threshold (default 20%)")


class MonteCarloSimulator:
    """Bootstrap and permutation engine for sequence-of-returns and ruin probability analysis.
    
    Guarantees Section 6 Trading Quality enhancement:
    - Demonstrates that performance is not an artifact of favorable trade sequencing.
    """

    def __init__(
        self,
        num_simulations: int = 500,
        initial_capital: Decimal = Decimal("10000.00"),
        ruin_threshold_pct: Decimal = Decimal("0.20"),
        seed: int = 42
    ) -> None:
        self.num_simulations = num_simulations
        self.initial_capital = initial_capital
        self.ruin_threshold_pct = ruin_threshold_pct
        self.seed = seed

    def run(self, trades: list[TradeRecord]) -> MonteCarloResult:
        if not trades:
            return MonteCarloResult(
                num_simulations=self.num_simulations,
                mean_final_equity=self.initial_capital,
                median_final_equity=self.initial_capital,
                p05_final_equity=self.initial_capital,
                max_drawdown_mean=Decimal("0.00"),
                max_drawdown_p95=Decimal("0.00"),
                max_drawdown_p99=Decimal("0.00"),
                ruin_probability=Decimal("0.00")
            )

        rng = random.Random(self.seed)
        final_equities: list[Decimal] = []
        max_drawdowns: list[Decimal] = []
        ruin_count = 0
        ruin_level = self.initial_capital * (Decimal("1.0") - self.ruin_threshold_pct)

        trade_pnls = [t.pnl for t in trades]

        for _ in range(self.num_simulations):
            # Reshuffle trades with replacement
            sim_pnls = [rng.choice(trade_pnls) for _ in range(len(trade_pnls))]

            equity = self.initial_capital
            peak = self.initial_capital
            max_dd = Decimal("0.00")
            ruined = False

            for pnl in sim_pnls:
                equity += pnl
                peak = max(peak, equity)
                dd = ((peak - equity) / peak * Decimal("100.00")) if peak > Decimal(0) else Decimal("0.00")
                max_dd = max(max_dd, dd)
                if equity <= ruin_level:
                    ruined = True

            final_equities.append(equity)
            max_drawdowns.append(max_dd)
            if ruined:
                ruin_count += 1

        final_equities.sort()
        max_drawdowns.sort()

        n = len(final_equities)
        mean_equity = sum(final_equities, Decimal("0.00")) / Decimal(str(n))
        median_equity = final_equities[n // 2]
        p05_equity = final_equities[int(n * 0.05)]

        mean_dd = sum(max_drawdowns, Decimal("0.00")) / Decimal(str(n))
        p95_dd = max_drawdowns[int(n * 0.95)]
        p99_dd = max_drawdowns[min(int(n * 0.99), n - 1)]

        ruin_prob = Decimal(str(ruin_count)) / Decimal(str(self.num_simulations))

        return MonteCarloResult(
            num_simulations=self.num_simulations,
            mean_final_equity=mean_equity,
            median_final_equity=median_equity,
            p05_final_equity=p05_equity,
            max_drawdown_mean=mean_dd,
            max_drawdown_p95=p95_dd,
            max_drawdown_p99=p99_dd,
            ruin_probability=ruin_prob
        )
