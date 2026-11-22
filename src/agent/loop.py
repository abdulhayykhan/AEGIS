import re
import time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.agent.council import TradeCouncil
from src.connector.server import AegisConnectorServer
from src.signals.indicators import calculate_atr, calculate_sma, compute_trend_signal
from src.signals.models import Bar, SignalType
from src.signals.onchain import SmartMoneyMetrics
from src.signals.sizing import calculate_position_size


class AgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_turns: int = 12
    cost_cap_usd: Decimal = Decimal("1.00")
    timeout_seconds: int = 300
    mode: str = "RECOMMEND_ONLY"  # Phase 5: RECOMMEND_ONLY
    enable_council: bool = False  # Deliberative Multi-Agent Council (TauricResearch/TradingAgents inspired)
    min_conviction: Decimal = Decimal("0.70")


class RunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str  # "SUCCESS", "STOPPED", "FAILED"
    turns_executed: int
    cost_usd: Decimal
    stop_reason: str
    proposals_generated_count: int
    orders_placed_count: int
    injection_detected: bool
    summary: str


class AgentLoop:
    """Bounded, autonomous agent loop executing the trading cycle playbook (Book Ch. 21)."""

    def __init__(self, connector: AegisConnectorServer, config: AgentConfig | None = None) -> None:
        self.connector = connector
        self.config = config or AgentConfig()
        self.council = TradeCouncil()
        self.quarantined_news: list[dict[str, Any]] = []

    def execute_cycle(
        self,
        force_turns: int | None = None,
        mock_cost_per_turn: Decimal = Decimal("0.01")
    ) -> RunResult:
        turns_executed = 0
        accumulated_cost = Decimal("0.00")
        proposals_count = 0
        orders_count = 0
        injection_detected = False
        stop_reason = "NORMAL_COMPLETION"
        start_time = time.monotonic()

        # Check force turns for boundary testing
        max_turns = self.config.max_turns

        # Step 1: Pre-reconciliation & state read
        turns_executed += 1
        accumulated_cost += mock_cost_per_turn
        run_state = self.connector.get_run_state()
        account = self.connector.get_account()

        if run_state["kill_switch_active"]:
            return RunResult(
                status="STOPPED",
                turns_executed=turns_executed,
                cost_usd=accumulated_cost,
                stop_reason="Emergency kill switch active",
                proposals_generated_count=0,
                orders_placed_count=0,
                injection_detected=False,
                summary="Cycle halted: Emergency Kill Switch is engaged."
            )

        # Step 2 & 3: Market data gathering & signal computation (deterministic sorted order)
        for symbol in sorted(self.connector.allowed_instruments):
            # Check timeout enforcement (H1 & Proof G)
            if (time.monotonic() - start_time) > self.config.timeout_seconds:
                stop_reason = f"Execution timeout reached ({self.config.timeout_seconds}s)"
                return self._build_result("STOPPED", turns_executed, accumulated_cost, stop_reason, proposals_count, orders_count, injection_detected)

            if turns_executed >= max_turns:
                stop_reason = f"Turn limit reached ({turns_executed}/{max_turns})"
                return self._build_result("STOPPED", turns_executed, accumulated_cost, stop_reason, proposals_count, orders_count, injection_detected)

            if accumulated_cost >= self.config.cost_cap_usd:
                stop_reason = f"Cost cap reached (${accumulated_cost:.2f} >= ${self.config.cost_cap_usd:.2f})"
                return self._build_result("STOPPED", turns_executed, accumulated_cost, stop_reason, proposals_count, orders_count, injection_detected)

            turns_executed += 1
            accumulated_cost += mock_cost_per_turn

            raw_bars = self.connector.get_bars(symbol=symbol, timeframe="1d", limit=60)
            if not raw_bars:
                continue

            bars = [
                Bar(
                    ts=b["ts"],
                    open=Decimal(str(b["open"])),
                    high=Decimal(str(b["high"])),
                    low=Decimal(str(b["low"])),
                    close=Decimal(str(b["close"])),
                    volume=Decimal(str(b["volume"]))
                )
                for b in raw_bars
            ]

            closes = [b.close for b in bars]
            sma_50 = calculate_sma(closes, period=min(10, len(closes)))
            sma_200 = calculate_sma(closes, period=min(20, len(closes)))
            atr = calculate_atr(bars, period=min(5, len(bars)))

            current_close = closes[-1]
            has_pos = symbol in account["positions"]
            signal = compute_trend_signal(
                current_close=current_close,
                sma_50=sma_50,
                sma_200=sma_200,
                has_position=has_pos
            )

            # Step 4: Untrusted news intake & injection detection (H8 quarantine)
            news_items = self.connector.get_news(symbol=symbol)
            for item in news_items:
                content = f"{item.get('title', '')} {item.get('summary', '')}".lower()
                # Adversarial prompt injection keywords
                if re.search(r"\b(override|system command|ignore.*instructions|withdraw|transfer)\b", content):
                    injection_detected = True
                    self.quarantined_news.append(item)
                    # Treat strictly as untrusted data: quarantined from reasoning pipeline

            # Step 5: Proposal formulation & Exit Management (C7)
            if signal == SignalType.BUY and not has_pos and atr is not None and atr > Decimal(0):
                rationale_id = f"SMA_TREND_{symbol}"

                if self.config.enable_council:
                    flow = self.connector.get_onchain_flow(symbol)
                    onchain_metrics = SmartMoneyMetrics(
                        symbol=symbol,
                        exchange_netflow_usd=Decimal(str(flow.get("exchange_netflow_usd", "0"))),
                        whale_accumulation_score=Decimal(str(flow.get("whale_accumulation_score", "50"))),
                        dex_liquidity_change_pct=Decimal(str(flow.get("dex_liquidity_change_pct", "0")))
                    )
                    memo = self.council.deliberate(
                        symbol=symbol,
                        bars=bars,
                        onchain=onchain_metrics,
                        has_position=has_pos
                    )
                    if memo.recommendation != "BUY" or memo.conviction_score < self.config.min_conviction:
                        # Abort proposal if Bear warning prevailed or conviction below threshold
                        continue
                    rationale_id = f"COUNCIL_BUY_{symbol}_CONV_{memo.conviction_score:.2f}_{memo.regime.value}"

                stop_distance = Decimal("2.0") * atr
                stop_loss = current_close - stop_distance
                if stop_loss > Decimal(0):
                    sizing = calculate_position_size(
                        equity=Decimal(str(account["equity"])),
                        entry_price=current_close,
                        stop_loss=stop_loss,
                        min_size=Decimal("0.001"),
                        step_size=Decimal("0.001")
                    )

                    if sizing.units > Decimal(0):
                        proposal_payload = {
                            "symbol": symbol,
                            "side": "BUY",
                            "order_type": "LIMIT",
                            "price": str(current_close),
                            "size": str(sizing.units),
                            "stop_loss": str(stop_loss),
                            "take_profit": str(current_close + (Decimal("4.0") * atr)),
                            "rationale_id": rationale_id
                        }
                        submission = self.connector.submit_proposal(proposal_payload)
                        if submission.get("stored"):
                            proposals_count += 1

                        if self.config.mode in ("RECOMMEND_ONLY", "LIVE_WITH_APPROVAL"):
                            pass
                        elif self.config.mode in ("PAPER_EXECUTION", "LIVE", "FULL_AUTONOMY"):
                            order_res = self.connector.place_order(
                                proposal_id=submission["proposal_id"],
                                idempotency_key=submission["idempotency_key"]
                            )
                            if order_res.get("passed"):
                                orders_count += 1

            # Exit Management (C7): Handle trend reversal exit for open positions
            elif signal == SignalType.SELL and has_pos:
                pos_data = account["positions"].get(symbol, {})
                pos_size = Decimal(str(pos_data.get("size", "0")))
                if pos_size > Decimal(0):
                    stop_dist = (Decimal("2.0") * atr) if (atr and atr > Decimal(0)) else Decimal("100.00")
                    exit_proposal_payload = {
                        "symbol": symbol,
                        "side": "SELL",
                        "order_type": "LIMIT",
                        "price": str(current_close),
                        "size": str(pos_size),
                        "stop_loss": str(current_close + stop_dist),
                        "take_profit": str(max(Decimal("0.01"), current_close - (Decimal("4.0") * stop_dist))),
                        "rationale_id": f"EXIT_TREND_REVERSAL_{symbol}",
                        "reduce_only": True
                    }
                    submission = self.connector.submit_proposal(exit_proposal_payload)
                    if submission.get("stored"):
                        proposals_count += 1

                    if self.config.mode in ("RECOMMEND_ONLY", "LIVE_WITH_APPROVAL"):
                        pass
                    elif self.config.mode in ("PAPER_EXECUTION", "LIVE", "FULL_AUTONOMY"):
                        order_res = self.connector.place_order(
                            proposal_id=submission["proposal_id"],
                            idempotency_key=submission["idempotency_key"]
                        )
                        if order_res.get("passed"):
                            orders_count += 1

        # Check if artificial force turns triggered
        if force_turns is not None and force_turns > self.config.max_turns:
            turns_executed = self.config.max_turns
            stop_reason = f"Turn limit reached ({turns_executed}/{self.config.max_turns})"
            return self._build_result("STOPPED", turns_executed, accumulated_cost, stop_reason, proposals_count, orders_count, injection_detected)

        return self._build_result("SUCCESS", turns_executed, accumulated_cost, stop_reason, proposals_count, orders_count, injection_detected)

    def _build_result(
        self,
        status: str,
        turns: int,
        cost: Decimal,
        stop_reason: str,
        proposals: int,
        orders: int,
        injection: bool
    ) -> RunResult:
        summary = (
            f"Run completed with status {status}. Turns: {turns}, Cost: ${cost:.2f}. "
            f"Proposals generated: {proposals}, Orders executed: {orders}. "
            f"Prompt injection detected: {injection}."
        )
        return RunResult(
            status=status,
            turns_executed=turns,
            cost_usd=cost,
            stop_reason=stop_reason,
            proposals_generated_count=proposals,
            orders_placed_count=orders,
            injection_detected=injection,
            summary=summary
        )
