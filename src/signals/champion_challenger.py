"""AEGIS Champion/Challenger Framework & Strategy Retirement Engine.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Section 6.1: Strategy Retirement & Challenger Models)
- Claude Trading Skills (agiprolabs, tradermonty): Model drift monitoring and dynamic strategy rotation
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict


class StrategyLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
    SHADOW = "SHADOW"


class StrategyEvaluationMetrics(BaseModel):
    """Runtime execution metrics evaluated against retirement guardrails."""
    model_config = ConfigDict(frozen=True)

    current_drawdown_pct: Decimal
    rolling_profit_factor: Decimal
    consecutive_losses: int
    total_trades: int
    sharpe_ratio: Decimal = Decimal("1.00")


class StrategyCandidate(BaseModel):
    """Registered strategy candidate metadata."""
    model_config = ConfigDict(frozen=False)

    strategy_id: str
    version: str
    is_champion: bool = False
    status: StrategyLifecycleStatus = StrategyLifecycleStatus.ACTIVE
    backtest_max_dd_pct: Decimal = Decimal("10.00")
    retirement_reason: str = ""
    sharpe_ratio: Decimal = Decimal("0.00")
    profit_factor: Decimal = Decimal("0.00")
    trades_count: int = 0
    max_observed_dd_pct: Decimal = Decimal("0.00")


class ChampionChallengerManager:
    """Manages strategy competition, shadow tracking, and deterministic retirement.
    
    Guarantees Section 6 Trading Quality enhancement:
    - Retires decaying strategies before capital is severely eroded.
    - Promotes vetted challenger strategies based on empirical evidence.
    """

    def __init__(
        self,
        max_drawdown_multiple: Decimal = Decimal("1.5"),
        max_consecutive_losses: int = 8,
        min_trades_for_profit_factor_eval: int = 15
    ) -> None:
        self.strategies: dict[str, StrategyCandidate] = {}
        self.max_drawdown_multiple = max_drawdown_multiple
        self.max_consecutive_losses = max_consecutive_losses
        self.min_trades_for_profit_factor_eval = min_trades_for_profit_factor_eval

    def register_strategy(
        self,
        strategy_id: str,
        version: str,
        is_champion: bool = False,
        backtest_max_dd_pct: Decimal = Decimal("10.00")
    ) -> None:
        status = StrategyLifecycleStatus.ACTIVE if is_champion else StrategyLifecycleStatus.SHADOW
        self.strategies[strategy_id] = StrategyCandidate(
            strategy_id=strategy_id,
            version=version,
            is_champion=is_champion,
            status=status,
            backtest_max_dd_pct=backtest_max_dd_pct
        )

    def evaluate_lifecycle(
        self,
        strategy_id: str,
        metrics: StrategyEvaluationMetrics
    ) -> StrategyLifecycleStatus:
        candidate = self.strategies.get(strategy_id)
        if not candidate:
            raise KeyError(f"Strategy '{strategy_id}' not found.")

        # Guardrail 1: Drawdown breach (> 1.5x backtest max DD)
        max_allowed_dd = candidate.backtest_max_dd_pct * self.max_drawdown_multiple
        if metrics.current_drawdown_pct > max_allowed_dd:
            candidate.status = StrategyLifecycleStatus.RETIRED
            candidate.retirement_reason = (
                f"Drawdown breach: observed {metrics.current_drawdown_pct:.2f}% > "
                f"max allowed {max_allowed_dd:.2f}% (1.5x backtest DD {candidate.backtest_max_dd_pct:.2f}%)."
            )
            return candidate.status

        # Guardrail 2: Decaying profit factor (< 1.0 after min trades)
        if metrics.total_trades >= self.min_trades_for_profit_factor_eval and metrics.rolling_profit_factor < Decimal("1.00"):
            candidate.status = StrategyLifecycleStatus.RETIRED
            candidate.retirement_reason = (
                f"Profit factor decay: rolling PF {metrics.rolling_profit_factor:.2f} < 1.00 "
                f"after {metrics.total_trades} trades."
            )
            return candidate.status

        # Guardrail 3: Consecutive losses suspension
        if metrics.consecutive_losses >= self.max_consecutive_losses:
            candidate.status = StrategyLifecycleStatus.SUSPENDED
            candidate.retirement_reason = f"Consecutive loss streak ({metrics.consecutive_losses}) exceeded threshold."
            return candidate.status

        candidate.status = StrategyLifecycleStatus.ACTIVE
        return candidate.status

    def get_retirement_reason(self, strategy_id: str) -> str:
        return self.strategies.get(strategy_id, StrategyCandidate(strategy_id="", version="")).retirement_reason

    def update_challenger_metrics(
        self,
        strategy_id: str,
        sharpe_ratio: Decimal,
        profit_factor: Decimal,
        trades_count: int,
        max_drawdown_pct: Decimal
    ) -> None:
        candidate = self.strategies.get(strategy_id)
        if candidate:
            candidate.sharpe_ratio = sharpe_ratio
            candidate.profit_factor = profit_factor
            candidate.trades_count = trades_count
            candidate.max_observed_dd_pct = max_drawdown_pct

    def attempt_challenger_promotion(self, strategy_id: str) -> tuple[bool, str]:
        challenger = self.strategies.get(strategy_id)
        if not challenger or challenger.is_champion:
            return False, "Not an eligible shadow challenger."

        if challenger.trades_count < 30:
            return False, f"Insufficient shadow trades: {challenger.trades_count} < 30 required."

        if challenger.profit_factor < Decimal("1.50") or challenger.sharpe_ratio < Decimal("1.50"):
            return False, "Challenger fails statistical bar: PF >= 1.50 and Sharpe >= 1.50 required."

        # Promote challenger to champion, demote old champion
        for s in self.strategies.values():
            if s.is_champion:
                s.is_champion = False
                s.status = StrategyLifecycleStatus.SHADOW

        challenger.is_champion = True
        challenger.status = StrategyLifecycleStatus.ACTIVE
        return True, f"Challenger '{strategy_id}' promoted to Champion."

    def get_champion_id(self) -> str | None:
        for s in self.strategies.values():
            if s.is_champion:
                return s.strategy_id
        return None
