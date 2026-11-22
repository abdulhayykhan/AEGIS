from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.signals.models import Bar, SignalType
from src.signals.sizing import calculate_position_size
from src.signals.strategy import StrategyConfig, evaluate_strategy


class BacktestConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial_capital: Decimal = Decimal("10000.0")
    fee_rate: Decimal = Decimal("0.001")          # 0.10% taker fee
    slippage_rate: Decimal = Decimal("0.0005")    # 0.05% slippage on fills
    fast_period: int = 50
    slow_period: int = 200
    atr_period: int = 14


class TradeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_ts: int
    exit_ts: int
    entry_price: Decimal
    exit_price: Decimal
    units: Decimal
    pnl: Decimal
    fee_paid: Decimal
    slippage_loss: Decimal
    exit_reason: str


class DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_bar_ts: int
    decision_bar_ts: int
    signal: str


class BacktestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial_capital: Decimal
    final_equity: Decimal
    total_return_pct: Decimal
    benchmark_return_pct: Decimal
    max_drawdown_pct: Decimal
    trades: list[TradeRecord]
    equity_curve: list[tuple[int, Decimal]]
    decision_history: list[DecisionRecord]


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(self, bars: list[Bar]) -> BacktestResult:
        if not bars:
            raise ValueError("Cannot run backtest on empty bar dataset.")

        cash = self.config.initial_capital
        peak_equity = self.config.initial_capital
        max_drawdown_pct = Decimal("0.0")
        
        position_units = Decimal("0.0")
        position_entry_price = Decimal("0.0")
        position_stop_loss = Decimal("0.0")
        position_entry_ts = 0

        trades: list[TradeRecord] = []
        equity_curve: list[tuple[int, Decimal]] = []
        decision_history: list[DecisionRecord] = []

        # Benchmark calculation (Buy & Hold)
        first_price = bars[0].close
        last_price = bars[-1].close
        benchmark_return_pct = ((last_price - first_price) / first_price) * Decimal("100.0")

        # For shorter test samples, dynamically scale periods if bars count < slow_period
        fast_period = self.config.fast_period
        slow_period = self.config.slow_period
        atr_period = self.config.atr_period

        if len(bars) < slow_period:
            fast_period = max(3, len(bars) // 4)
            slow_period = max(5, len(bars) // 2)
            atr_period = max(3, len(bars) // 5)

        for i in range(len(bars)):
            # Strictly slice bars up to current index i (ZERO LOOKAHEAD)
            visible_bars = bars[: i + 1]
            current_bar = visible_bars[-1]
            current_ts = current_bar.ts

            # Record decision audit
            decision_history.append(
                DecisionRecord(
                    current_bar_ts=current_ts,
                    decision_bar_ts=visible_bars[-1].ts,
                    signal=""
                )
            )

            current_price = current_bar.close

            # Check stop loss if holding position (accounting for gap-throughs)
            if position_units > Decimal(0) and current_bar.low <= position_stop_loss:
                # Stop loss triggered: gap-throughs fill at open if opened below stop price
                fill_price = min(position_stop_loss, current_bar.open)
                effective_exit = fill_price * (Decimal("1.0") - self.config.slippage_rate)
                slippage_loss = (fill_price - effective_exit) * position_units
                fee = (effective_exit * position_units) * self.config.fee_rate
                gross_pnl = (effective_exit - position_entry_price) * position_units
                net_pnl = gross_pnl - fee

                cash += (effective_exit * position_units) - fee
                trades.append(
                    TradeRecord(
                        entry_ts=position_entry_ts,
                        exit_ts=current_ts,
                        entry_price=position_entry_price,
                        exit_price=effective_exit,
                        units=position_units,
                        pnl=net_pnl,
                        fee_paid=fee,
                        slippage_loss=slippage_loss,
                        exit_reason="STOP_LOSS"
                    )
                )
                position_units = Decimal("0.0")

            # Evaluate unified strategy logic
            has_pos = position_units > Decimal(0)
            strat_res = evaluate_strategy(
                visible_bars,
                has_position=has_pos,
                config=StrategyConfig(
                    fast_period=fast_period,
                    slow_period=slow_period,
                    atr_period=atr_period,
                    min_warmup_bars=slow_period,
                    regime_filter_enabled=False  # Keep raw backtest baseline comparable
                )
            )
            signal = strat_res.signal
            atr = strat_res.atr

            # Update signal in decision history
            decision_history[-1] = DecisionRecord(
                current_bar_ts=current_ts,
                decision_bar_ts=visible_bars[-1].ts,
                signal=signal.value
            )

            # Process Exit Signal
            if signal == SignalType.SELL and position_units > Decimal(0):
                effective_exit = current_price * (Decimal("1.0") - self.config.slippage_rate)
                slippage_loss = (current_price - effective_exit) * position_units
                fee = (effective_exit * position_units) * self.config.fee_rate
                gross_pnl = (effective_exit - position_entry_price) * position_units
                net_pnl = gross_pnl - fee

                cash += (effective_exit * position_units) - fee
                trades.append(
                    TradeRecord(
                        entry_ts=position_entry_ts,
                        exit_ts=current_ts,
                        entry_price=position_entry_price,
                        exit_price=effective_exit,
                        units=position_units,
                        pnl=net_pnl,
                        fee_paid=fee,
                        slippage_loss=slippage_loss,
                        exit_reason="TREND_REVERSAL"
                    )
                )
                position_units = Decimal("0.0")

            # Process Entry Signal
            elif (
                signal == SignalType.BUY
                and position_units == Decimal(0)
                and atr is not None
                and atr > Decimal(0)
            ):
                stop_distance = Decimal("2.0") * atr
                stop_loss_price = current_price - stop_distance
                if stop_loss_price > Decimal(0):
                    current_equity = cash
                    sizing = calculate_position_size(
                        equity=current_equity,
                        entry_price=current_price,
                        stop_loss=stop_loss_price,
                        min_size=Decimal("0.001"),
                        step_size=Decimal("0.001")
                    )

                    if sizing.units > Decimal(0):
                        effective_entry = current_price * (Decimal("1.0") + self.config.slippage_rate)
                        fee = (effective_entry * sizing.units) * self.config.fee_rate
                        total_cost = (effective_entry * sizing.units) + fee

                        if total_cost <= cash:
                            cash -= total_cost
                            position_units = sizing.units
                            position_entry_price = effective_entry
                            position_stop_loss = stop_loss_price
                            position_entry_ts = current_ts


            # Calculate current total equity
            current_portfolio_value = cash + (position_units * current_price)
            equity_curve.append((current_ts, current_portfolio_value))

            peak_equity = max(peak_equity, current_portfolio_value)
            drawdown = (peak_equity - current_portfolio_value) / peak_equity * Decimal("100.0")
            max_drawdown_pct = max(max_drawdown_pct, drawdown)

        # Close any open position at end of backtest for final accounting
        if position_units > Decimal(0):
            final_exit = bars[-1].close * (Decimal("1.0") - self.config.slippage_rate)
            fee = (final_exit * position_units) * self.config.fee_rate
            net_pnl = ((final_exit - position_entry_price) * position_units) - fee
            cash += (final_exit * position_units) - fee
            trades.append(
                TradeRecord(
                    entry_ts=position_entry_ts,
                    exit_ts=bars[-1].ts,
                    entry_price=position_entry_price,
                    exit_price=final_exit,
                    units=position_units,
                    pnl=net_pnl,
                    fee_paid=fee,
                    slippage_loss=(bars[-1].close - final_exit) * position_units,
                    exit_reason="END_OF_TEST"
                )
            )
            position_units = Decimal("0.0")

        final_equity = cash
        total_return_pct = ((final_equity - self.config.initial_capital) / self.config.initial_capital) * Decimal("100.0")

        return BacktestResult(
            initial_capital=self.config.initial_capital,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            trades=trades,
            equity_curve=equity_curve,
            decision_history=decision_history
        )
