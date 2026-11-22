"""AEGIS Empirical Multi-Asset Backtest & Robustness Runner.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Section 5 Step 3.3 & Finding H5)
"""

from decimal import Decimal
from pathlib import Path

from backtest.engine import BacktestConfig, BacktestEngine
from backtest.monte_carlo import MonteCarloSimulator
from backtest.report import generate_backtest_report
from backtest.walk_forward import WalkForwardOptimizer
from src.signals.data_loader import HistoricalDataLoader


def main() -> None:
    loader = HistoricalDataLoader()
    btc_bars = loader.get_or_fetch_bars("BTC/USDT", "1d")
    eth_bars = loader.get_or_fetch_bars("ETH/USDT", "1d")

    config = BacktestConfig(
        initial_capital=Decimal("10000.00"),
        fee_rate=Decimal("0.001"),       # 0.10% taker fee
        slippage_rate=Decimal("0.0005"),  # 0.05% fill slippage
        fast_period=50,
        slow_period=200,
        atr_period=14
    )

    # 1. Primary Backtest on BTC/USDT
    engine_btc = BacktestEngine(config=config)
    btc_result = engine_btc.run(btc_bars)

    # 2. Secondary Backtest on ETH/USDT
    engine_eth = BacktestEngine(config=config)
    eth_result = engine_eth.run(eth_bars)

    # 3. Walk-Forward Optimization on BTC/USDT
    wfo = WalkForwardOptimizer(train_window=250, test_window=100, step_size=100)
    wfo_result = wfo.run(btc_bars)

    # 4. Monte Carlo Simulation on BTC trades
    mc = MonteCarloSimulator(num_simulations=500, initial_capital=config.initial_capital)
    mc_result = mc.run(btc_result.trades)

    # 5. Compile and Write Report
    report_md = generate_backtest_report(
        result=btc_result,
        asset_name="BTC/USDT",
        wfo_result=wfo_result,
        mc_result=mc_result,
        secondary_results={"ETH/USDT": eth_result}
    )

    output_path = Path("docs/backtest-report.md")
    output_path.write_text(report_md, encoding="utf-8")
    print(
        f"Empirical Backtest Complete! Saved to {output_path}.\n"
        f"BTC Trades: {len(btc_result.trades)}, Final: ${btc_result.final_equity:,.2f}, MaxDD: {btc_result.max_drawdown_pct:.2f}%\n"
        f"ETH Trades: {len(eth_result.trades)}, Final: ${eth_result.final_equity:,.2f}, MaxDD: {eth_result.max_drawdown_pct:.2f}%"
    )


if __name__ == "__main__":
    main()
