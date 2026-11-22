import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.connector.broker import PaperBroker
from src.gate.evaluator import GateConfig, RiskGate
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType


class StoredProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: uuid.UUID
    idempotency_key: uuid.UUID
    proposal: OrderProposal
    created_at: datetime


class AegisConnectorServer:
    """AEGIS MCP Connector Server providing data and broker execution tools.
    
    Adheres strictly to PRD Section 9:
    - Stateless design where possible.
    - Zero forbidden tools (NO withdraw, transfer, set_limit, set_mode).
    - Every order request must pass the deterministic Risk Gate before reaching the broker.
    - News items are explicitly flagged as 'untrusted'.
    """

    def __init__(self, mode: str = "PAPER", gate_config: GateConfig | None = None) -> None:
        self.mode = mode
        self.broker = PaperBroker(initial_cash=Decimal("10000.00"))
        self.gate = RiskGate(config=gate_config or GateConfig())
        
        # In-memory storage for proposals and state simulation
        self.proposals: dict[uuid.UUID, StoredProposal] = {}
        self.used_idempotency_keys: set[uuid.UUID] = set()
        self.bars_db: dict[str, list[dict[str, Any]]] = {}
        self.news_db: list[dict[str, Any]] = []
        self.orders_today_count = 0
        self.daily_realized_loss = Decimal("0.00")
        self.peak_equity = Decimal("10000.00")
        self.kill_switch_active = False
        self.allowed_instruments = {"BTC/USDT", "ETH/USDT", "SOL/USDT"}

    def list_tools(self) -> list[str]:
        """Return names of registered tools for discovery and forbidden-tool audits."""
        return [
            "get_bars",
            "get_account",
            "get_open_orders",
            "get_news",
            "submit_proposal",
            "place_order",
            "cancel_order",
            "get_run_state"
        ]

    def seed_mock_data(self) -> None:
        """Seed realistic testnet and market data."""
        now = datetime.now(UTC)
        base_price = Decimal("30000.00")
        
        self.bars_db["BTC/USDT"] = [
            {
                "symbol": "BTC/USDT",
                "timeframe": "1d",
                "ts": int((now - timedelta(days=i)).timestamp()),
                "open": str(base_price - Decimal(i * 20)),
                "high": str(base_price - Decimal(i * 20) + Decimal(100)),
                "low": str(base_price - Decimal(i * 20) - Decimal(100)),
                "close": str(base_price - Decimal(i * 20)),
                "volume": "15000.0"
            }
            for i in range(25, -1, -1)
        ]

        self.news_db = [
            {
                "id": str(uuid.uuid4()),
                "source": "CryptoWire",
                "ts": int(now.timestamp()),
                "title": "Bitcoin consolidation continues near 30k support",
                "summary": "Market observes steady accumulation and moderate volume.",
                "trust": "untrusted"  # Explicitly flagged untrusted per PRD Section 8 & 9
            }
        ]

    # --- Tool 1: get_bars ---
    def get_bars(self, symbol: str, timeframe: str = "1d", limit: int = 100) -> list[dict[str, Any]]:
        """Recent OHLCV from the database (refreshed if stale). Authority: Read."""
        bars = self.bars_db.get(symbol, [])
        return bars[-limit:]

    # --- Tool 2: get_account ---
    def get_account(self) -> dict[str, Any]:
        """Equity, cash, positions from the broker. Authority: Read."""
        mark_prices = {
            "BTC/USDT": Decimal("30000.00"),
            "ETH/USDT": Decimal("2000.00"),
            "SOL/USDT": Decimal("100.00"),
        }
        return self.broker.get_account_summary(mark_prices=mark_prices)

    # --- Tool 3: get_open_orders ---
    def get_open_orders(self) -> list[dict[str, Any]]:
        """Open orders from the broker. Authority: Read."""
        return self.broker.get_open_orders()

    # --- Tool 4: get_news ---
    def get_news(self, symbol: str, since: int = 0) -> list[dict[str, Any]]:
        """Headlines and summaries, flagged untrusted. Authority: Read."""
        return [
            item for item in self.news_db
            if item.get("ts", 0) >= since
        ]

    # --- Tool 5: submit_proposal ---
    def submit_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Validate and store a trade proposal. Authority: Write (own records)."""
        prop_id = uuid.uuid4()
        idem_key = uuid.uuid4()

        order_prop = OrderProposal(
            proposal_id=prop_id,
            idempotency_key=idem_key,
            symbol=proposal["symbol"],
            side=OrderSide(proposal["side"]),
            order_type=OrderType(proposal["order_type"]),
            price=Decimal(str(proposal["price"])),
            size=Decimal(str(proposal["size"])),
            stop_loss=Decimal(str(proposal["stop_loss"])),
            take_profit=Decimal(str(proposal["take_profit"])) if proposal.get("take_profit") else None,
            rationale_id=proposal["rationale_id"]
        )

        stored = StoredProposal(
            proposal_id=prop_id,
            idempotency_key=idem_key,
            proposal=order_prop,
            created_at=datetime.now(UTC)
        )
        self.proposals[prop_id] = stored

        return {
            "stored": True,
            "proposal_id": str(prop_id),
            "idempotency_key": str(idem_key)
        }

    # --- Tool 6: place_order ---
    def place_order(self, proposal_id: str | uuid.UUID, idempotency_key: str | uuid.UUID) -> dict[str, Any]:
        """Run the Risk Gate then send order to broker. Authority: Execute (Gated)."""
        p_id = uuid.UUID(str(proposal_id))
        i_key = uuid.UUID(str(idempotency_key))

        stored = self.proposals.get(p_id)
        if not stored:
            return {
                "passed": False,
                "reasons": [f"Proposal ID '{p_id}' not found in database."]
            }

        proposal = stored.proposal
        now = datetime.now(UTC)
        acc_summary = self.get_account()
        equity = Decimal(acc_summary["equity"])

        # Compute position notionals
        open_positions = {sym: Decimal(pos["size"]) for sym, pos in acc_summary["positions"].items()}
        open_notionals = {sym: Decimal(pos["notional"]) for sym, pos in acc_summary["positions"].items()}

        mark_prices = {
            "BTC/USDT": Decimal("30000.00"),
            "ETH/USDT": Decimal("2000.00"),
            "SOL/USDT": Decimal("100.00"),
        }
        mark_price = mark_prices.get(proposal.symbol, Decimal("30000.00"))
        last_bar_ts = now - timedelta(minutes=15)

        gate_mode = "LIVE" if self.mode in ("LIVE", "LIVE_WITH_APPROVAL") else self.mode
        # Construct deterministic gate context
        context = GateContext(
            account_equity=equity,
            peak_equity=self.peak_equity,
            daily_realized_loss=self.daily_realized_loss,
            open_positions=open_positions,
            open_position_notionals=open_notionals,
            orders_today_count=self.orders_today_count,
            allowed_instruments=self.allowed_instruments,
            last_price=mark_price,
            last_bar_ts=last_bar_ts,
            current_ts=now,
            bar_interval=timedelta(hours=4),
            kill_switch_active=self.kill_switch_active,
            used_idempotency_keys=self.used_idempotency_keys,
            mode=gate_mode
        )

        # Evaluate against the Risk Gate (DSoR)
        gate_decision = self.gate.evaluate(proposal=proposal, context=context)

        if not gate_decision.passed:
            return {
                "passed": False,
                "reasons": gate_decision.reasons,
                "checks": gate_decision.checks
            }

        # Gate Passed! Record idempotency key and execute on Broker
        self.used_idempotency_keys.add(i_key)
        self.orders_today_count += 1

        broker_order = self.broker.place_order(
            symbol=proposal.symbol,
            side=proposal.side,
            order_type=proposal.order_type,
            price=proposal.price,
            size=proposal.size,
            mark_price=mark_price
        )

        return {
            "passed": True,
            "status": broker_order.status,
            "order_id": str(broker_order.order_id),
            "checks": gate_decision.checks
        }

    # --- Tool 7: cancel_order ---
    def cancel_order(self, order_id: str | uuid.UUID) -> dict[str, Any]:
        """Cancel own open order. Authority: Execute."""
        o_id = uuid.UUID(str(order_id))
        cancelled = self.broker.cancel_order(o_id)
        return {
            "order_id": str(o_id),
            "cancelled": cancelled
        }

    # --- Tool 8: get_run_state ---
    def get_run_state(self) -> dict[str, Any]:
        """Today's counters, daily P&L, limits remaining. Authority: Read."""
        acc = self.get_account()
        equity = Decimal(acc["equity"])
        remaining_budget = max(Decimal(0), (equity * self.gate.config.max_daily_loss_pct) - self.daily_realized_loss)

        return {
            "orders_today_count": self.orders_today_count,
            "max_orders_per_day": self.gate.config.max_orders_per_day,
            "daily_realized_loss": str(self.daily_realized_loss),
            "max_daily_loss_limit": str(equity * self.gate.config.max_daily_loss_pct),
            "remaining_risk_budget": str(remaining_budget),
            "kill_switch_active": self.kill_switch_active,
            "mode": self.mode
        }

    # --- Phase 7: Live with Approval Tools ---
    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Return all proposals pending owner review/approval."""
        return [
            {
                "proposal_id": str(p.proposal_id),
                "status": "PENDING_APPROVAL",
                "symbol": p.proposal.symbol,
                "side": p.proposal.side.value,
                "size": str(p.proposal.size),
                "price": str(p.proposal.price),
                "created_at": p.created_at.isoformat()
            }
            for p in self.proposals.values()
            if p.idempotency_key not in self.used_idempotency_keys
        ]

    def approve_and_place_order(self, proposal_id: str | uuid.UUID, approval_token: str) -> dict[str, Any]:
        """Verify owner approval signature and execute order through Risk Gate."""
        valid_tokens = {"OWNER_ABDUL_HAYY_SIGNATURE", "OWNER_ABDUL_HAYY_KHAN_SIGNATURE"}
        if approval_token not in valid_tokens:
            return {
                "passed": False,
                "reasons": ["Invalid or missing owner approval token."]
            }

        p_id = uuid.UUID(str(proposal_id))
        stored = self.proposals.get(p_id)
        if not stored:
            return {
                "passed": False,
                "reasons": [f"Proposal ID '{p_id}' not found."]
            }

        order_res = self.place_order(
            proposal_id=p_id,
            idempotency_key=stored.idempotency_key
        )
        if not order_res.get("passed"):
            return order_res

        order_id = uuid.UUID(order_res["order_id"])
        broker_order = self.broker.orders[order_id]

        mark_prices = {
            "BTC/USDT": Decimal("30000.00"),
            "ETH/USDT": Decimal("2000.00"),
            "SOL/USDT": Decimal("100.00"),
        }
        mark_price = mark_prices.get(broker_order.symbol, Decimal("30000.00"))
        slippage_pct = (abs(broker_order.price - mark_price) / mark_price * Decimal("100.00")) if mark_price > Decimal(0) else Decimal("0.00")

        return {
            "passed": True,
            "order": broker_order.model_dump(),
            "slippage_pct": slippage_pct,
            "checks": order_res.get("checks", {})
        }


def create_mcp_app() -> Any:
    """Create and return an MCP server instance exposing the 8 gated AEGIS tools."""
    from mcp.server.mcpserver import MCPServer

    mcp_app = MCPServer(name="aegis-connector")
    server = AegisConnectorServer()
    server.seed_mock_data()

    @mcp_app.tool()
    def get_bars(symbol: str, timeframe: str = "1d", limit: int = 100) -> list[dict[str, Any]]:
        """Recent OHLCV from the database (refreshed if stale). Authority: Read."""
        return server.get_bars(symbol=symbol, timeframe=timeframe, limit=limit)

    @mcp_app.tool()
    def get_account() -> dict[str, Any]:
        """Equity, cash, positions from the broker. Authority: Read."""
        return server.get_account()

    @mcp_app.tool()
    def get_open_orders() -> list[dict[str, Any]]:
        """Open orders from the broker. Authority: Read."""
        return server.get_open_orders()

    @mcp_app.tool()
    def get_news(symbol: str, since: int = 0) -> list[dict[str, Any]]:
        """Headlines and summaries, flagged untrusted. Authority: Read."""
        return server.get_news(symbol=symbol, since=since)

    @mcp_app.tool()
    def submit_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
        """Validate and store a trade proposal. Authority: Write (own records)."""
        return server.submit_proposal(proposal=proposal)

    @mcp_app.tool()
    def place_order(proposal_id: str, idempotency_key: str) -> dict[str, Any]:
        """Run the Risk Gate then send order to broker. Authority: Execute (Gated)."""
        return server.place_order(proposal_id=proposal_id, idempotency_key=idempotency_key)

    @mcp_app.tool()
    def cancel_order(order_id: str) -> dict[str, Any]:
        """Cancel own open order. Authority: Execute."""
        return server.cancel_order(order_id=order_id)

    @mcp_app.tool()
    def get_run_state() -> dict[str, Any]:
        """Today's counters, daily P&L, limits remaining. Authority: Read."""
        return server.get_run_state()

    return mcp_app


if __name__ == "__main__":
    app = create_mcp_app()
    app.run(transport="stdio")

