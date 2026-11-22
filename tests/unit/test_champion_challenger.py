from decimal import Decimal

from src.signals.champion_challenger import (
    ChampionChallengerManager,
    StrategyEvaluationMetrics,
    StrategyLifecycleStatus,
)


def test_champion_challenger_lifecycle_normal() -> None:
    mgr = ChampionChallengerManager()
    mgr.register_strategy(
        strategy_id="SMA_TREND_V1",
        version="1.0.0",
        is_champion=True,
        backtest_max_dd_pct=Decimal("5.00")
    )
    status = mgr.evaluate_lifecycle(
        strategy_id="SMA_TREND_V1",
        metrics=StrategyEvaluationMetrics(
            current_drawdown_pct=Decimal("3.20"),
            rolling_profit_factor=Decimal("1.80"),
            consecutive_losses=2,
            total_trades=25
        )
    )
    assert status == StrategyLifecycleStatus.ACTIVE


def test_champion_retired_on_drawdown_breach() -> None:
    mgr = ChampionChallengerManager()
    mgr.register_strategy(
        strategy_id="SMA_TREND_V1",
        version="1.0.0",
        is_champion=True,
        backtest_max_dd_pct=Decimal("5.00")  # Max allowed DD = 1.5 * 5.00 = 7.50%
    )
    # Current DD is 8.00% > 7.50% limit!
    status = mgr.evaluate_lifecycle(
        strategy_id="SMA_TREND_V1",
        metrics=StrategyEvaluationMetrics(
            current_drawdown_pct=Decimal("8.00"),
            rolling_profit_factor=Decimal("1.20"),
            consecutive_losses=3,
            total_trades=30
        )
    )
    assert status == StrategyLifecycleStatus.RETIRED
    assert "Drawdown breach" in mgr.get_retirement_reason("SMA_TREND_V1")


def test_challenger_promotion_to_champion() -> None:
    mgr = ChampionChallengerManager()
    mgr.register_strategy("CHAMPION_V1", "1.0", is_champion=True, backtest_max_dd_pct=Decimal("6.0"))
    mgr.register_strategy("CHALLENGER_V2", "2.0", is_champion=False, backtest_max_dd_pct=Decimal("4.0"))

    # Update challenger metrics with superior results
    mgr.update_challenger_metrics(
        strategy_id="CHALLENGER_V2",
        sharpe_ratio=Decimal("2.10"),
        profit_factor=Decimal("2.40"),
        trades_count=35,
        max_drawdown_pct=Decimal("3.50")
    )

    promoted, _msg = mgr.attempt_challenger_promotion("CHALLENGER_V2")
    assert promoted is True
    assert mgr.get_champion_id() == "CHALLENGER_V2"
