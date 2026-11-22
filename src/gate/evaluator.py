import hashlib
import hmac
import os
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.gate.kill_switch import StandaloneKillSwitch
from src.gate.models import GateContext, GateDecisionResult, OrderProposal, OrderSide, OrderType
from src.signals.freshness import verify_bar_freshness


class GateConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_risk_pct: Decimal = Decimal("0.01")       # 1% per-trade risk
    max_position_pct: Decimal = Decimal("0.10")   # 10% max instrument allocation
    max_exposure_pct: Decimal = Decimal("0.50")   # 50% max portfolio exposure
    max_open_positions: int = 3
    max_orders_per_day: int = 10                  # Aligned single config: 10 orders per day
    max_daily_loss_pct: Decimal = Decimal("0.02") # 2% daily loss limit
    max_drawdown_pct: Decimal = Decimal("0.10")   # Aligned single config: 10% peak drawdown limit
    price_sanity_pct: Decimal = Decimal("0.02")   # 2% price deviation limit


class RiskGate:
    """Deterministic Risk Gate (DSoR) implementing all safeguards without LLM heuristics."""

    def __init__(self, config: GateConfig | None = None) -> None:
        self.config = config or GateConfig()

    def evaluate(self, proposal: OrderProposal, context: GateContext) -> GateDecisionResult:
        checks_log: dict[str, bool] = {}
        failure_reasons: list[str] = []

        # 1. Kill switch and execution mode
        c1_reasons = self._check_kill_switch_and_mode(context)
        checks_log["kill_switch_and_mode"] = len(c1_reasons) == 0
        failure_reasons.extend(c1_reasons)

        # 2. Schema and order type (Limit/Stop-Limit only, positive values)
        c2_reasons = self._check_schema_and_order_type(proposal)
        checks_log["schema_and_order_type"] = len(c2_reasons) == 0
        failure_reasons.extend(c2_reasons)

        # 3. Allowlist and shorting checks
        c3_reasons = self._check_allowlist_and_shorting(proposal, context)
        checks_log["allowlist_and_shorting"] = len(c3_reasons) == 0
        failure_reasons.extend(c3_reasons)

        # 4. Data freshness & reconciliation
        c4_reasons = self._check_freshness_and_reconciliation(context)
        checks_log["freshness_and_reconciliation"] = len(c4_reasons) == 0
        failure_reasons.extend(c4_reasons)

        # 5. Portfolio limits: count, daily loss, drawdown, position size, exposure
        c5_reasons = self._check_portfolio_limits(proposal, context)
        checks_log["portfolio_limits"] = len(c5_reasons) == 0
        failure_reasons.extend(c5_reasons)

        # 6. Per-trade risk and price sanity
        c6_reasons = self._check_per_trade_risk(proposal, context)
        checks_log["per_trade_risk_and_sanity"] = len(c6_reasons) == 0
        failure_reasons.extend(c6_reasons)

        # 7. Idempotency guard
        c7_reasons = self._check_idempotency(proposal, context)
        checks_log["idempotency"] = len(c7_reasons) == 0
        failure_reasons.extend(c7_reasons)

        # 8. Envelope approval check (e.g. for small live approval)
        c8_reasons = self._check_approvals(proposal, context)
        checks_log["approvals"] = len(c8_reasons) == 0
        failure_reasons.extend(c8_reasons)

        passed = len(failure_reasons) == 0

        return GateDecisionResult(
            passed=passed,
            checks=checks_log,
            reasons=failure_reasons,
            decided_at=datetime.now(UTC)
        )

    def _check_kill_switch_and_mode(self, context: GateContext) -> list[str]:
        reasons: list[str] = []
        if context.kill_switch_active or StandaloneKillSwitch().is_engaged():
            reasons.append("Emergency Kill Switch is active. All order actions blocked.")
        if context.mode not in ("PAPER", "LIVE", "LIVE_WITH_APPROVAL"):
            reasons.append(f"Invalid execution mode: '{context.mode}'. Must be PAPER, LIVE, or LIVE_WITH_APPROVAL.")
        return reasons

    def _check_schema_and_order_type(self, proposal: OrderProposal) -> list[str]:
        reasons: list[str] = []
        if proposal.order_type == OrderType.MARKET:
            reasons.append("Market orders are strictly prohibited (Limit and Stop-Limit orders only).")
        if proposal.price <= Decimal(0):
            reasons.append(f"Price must be strictly positive (got {proposal.price}).")
        if proposal.size <= Decimal(0):
            reasons.append(f"Size must be strictly positive (got {proposal.size}).")
        return reasons

    def _check_allowlist_and_shorting(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        reasons: list[str] = []
        if proposal.symbol not in context.allowed_instruments:
            reasons.append(f"Instrument '{proposal.symbol}' is not on allow list.")

        # C7 & Proof B: Check shorting and oversell rules
        if proposal.side == OrderSide.SELL:
            held_position = context.open_positions.get(proposal.symbol, Decimal(0))
            if held_position <= Decimal(0):
                reasons.append(f"Shorting is disabled: cannot sell '{proposal.symbol}' with zero held position.")
            elif proposal.size > held_position:
                reasons.append(
                    f"Oversell rejected: attempted to sell {proposal.size} units but only {held_position} held."
                )

        return reasons

    def _check_freshness_and_reconciliation(self, context: GateContext) -> list[str]:
        reasons: list[str] = []
        is_fresh, freshness_msg = verify_bar_freshness(
            latest_bar_ts=context.last_bar_ts,
            current_ts=context.current_ts,
            bar_interval=context.bar_interval,
            max_bars_lag=2
        )
        if not is_fresh:
            reasons.append(freshness_msg)

        # C5: Explicit reconciliation match verification
        if not context.reconciliation_matched:
            reasons.append("Reconciliation mismatch detected between internal ledger and broker state.")

        return reasons

    def _check_portfolio_limits(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        reasons: list[str] = []
        equity = context.account_equity

        # C8 & Proof E: Reduce-only exits (closing or scaling down open positions) are exempt
        # from risk-adding limits (max open positions, daily loss, peak drawdown, max exposure)
        held_position = context.open_positions.get(proposal.symbol, Decimal(0))
        is_reduce_only = (
            proposal.reduce_only
            or context.reduce_only
            or (proposal.side == OrderSide.SELL and held_position > Decimal(0))
        )

        if not is_reduce_only:
            # Max open positions (3)
            is_new_symbol = proposal.symbol not in context.open_positions or held_position == Decimal(0)
            if is_new_symbol and len(context.open_positions) >= self.config.max_open_positions:
                reasons.append(
                    f"Max open positions reached ({len(context.open_positions)}/{self.config.max_open_positions})."
                )

            # Max daily loss (2% equity) - exits are exempt to allow loss minimization
            max_allowed_daily_loss = equity * self.config.max_daily_loss_pct
            if context.daily_realized_loss >= max_allowed_daily_loss:
                reasons.append(
                    f"Daily loss limit breached: {context.daily_realized_loss:.2f} >= max allowed {max_allowed_daily_loss:.2f} USDT."
                )

            # Max peak drawdown (10% from peak) - exits are exempt
            if context.peak_equity > Decimal(0):
                drawdown = (context.peak_equity - equity) / context.peak_equity
                if drawdown >= self.config.max_drawdown_pct:
                    reasons.append(
                        f"Peak drawdown limit breached: {drawdown * Decimal(100):.2f}% >= max allowed {self.config.max_drawdown_pct * Decimal(100):.2f}%."
                    )

            # Max instrument position size (10% equity)
            order_notional = proposal.price * proposal.size
            existing_instrument_notional = context.open_position_notionals.get(proposal.symbol, Decimal(0))
            total_instrument_notional = existing_instrument_notional + order_notional
            max_instrument_notional = equity * self.config.max_position_pct
            if total_instrument_notional > max_instrument_notional:
                reasons.append(
                    f"Max instrument position size exceeded: {total_instrument_notional:.2f} > {max_instrument_notional:.2f} USDT (10%)."
                )

            # Max total portfolio exposure (50% equity)
            current_total_exposure = sum(context.open_position_notionals.values(), Decimal(0))
            new_total_exposure = current_total_exposure + order_notional
            max_total_exposure = equity * self.config.max_exposure_pct
            if new_total_exposure > max_total_exposure:
                reasons.append(
                    f"Max total exposure exceeded: {new_total_exposure:.2f} > {max_total_exposure:.2f} USDT (50%)."
                )

        # Max orders per 24h window (Exempt reduce-only exit orders - B6 & Proof 3)
        if not is_reduce_only and context.orders_today_count >= self.config.max_orders_per_day:
            reasons.append(
                f"Daily order limit reached ({context.orders_today_count}/{self.config.max_orders_per_day})."
            )

        return reasons

    def _check_per_trade_risk(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        reasons: list[str] = []
        equity = context.account_equity

        held_position = context.open_positions.get(proposal.symbol, Decimal(0))
        is_reduce_only = (
            proposal.reduce_only
            or context.reduce_only
            or (proposal.side == OrderSide.SELL and held_position > Decimal(0))
        )

        # C8 & Proof D: Validate stop loss and take profit direction per side
        if proposal.side == OrderSide.BUY:
            if proposal.stop_loss >= proposal.price:
                reasons.append(
                    f"Invalid BUY stop loss: stop_loss ({proposal.stop_loss:.2f}) must be strictly below limit price ({proposal.price:.2f})."
                )
            if proposal.take_profit is not None and proposal.take_profit <= proposal.price:
                reasons.append(
                    f"Invalid BUY take profit: take_profit ({proposal.take_profit:.2f}) must be strictly above limit price ({proposal.price:.2f})."
                )
            stop_distance = proposal.price - proposal.stop_loss
        else:  # SELL
            if proposal.stop_loss <= proposal.price:
                reasons.append(
                    f"Invalid SELL stop loss: stop_loss ({proposal.stop_loss:.2f}) must be strictly above limit price ({proposal.price:.2f})."
                )
            if proposal.take_profit is not None and proposal.take_profit >= proposal.price:
                reasons.append(
                    f"Invalid SELL take profit: take_profit ({proposal.take_profit:.2f}) must be strictly below limit price ({proposal.price:.2f})."
                )
            stop_distance = proposal.stop_loss - proposal.price

        # Per-trade risk <= 1% equity (Exempt reduce-only exit orders - B6 & Proof 3)
        if not is_reduce_only and stop_distance > Decimal(0):
            monetary_risk = stop_distance * proposal.size
            max_trade_risk = equity * self.config.max_risk_pct

            if monetary_risk > max_trade_risk:
                reasons.append(
                    f"Max risk per trade exceeded: {monetary_risk:.2f} > {max_trade_risk:.2f} USDT (1%)."
                )

        # Price sanity <= 2% from last mark price
        if context.last_price > Decimal(0):
            price_dev = abs(proposal.price - context.last_price) / context.last_price
            if price_dev > self.config.price_sanity_pct:
                reasons.append(
                    f"Price sanity breach: limit price {proposal.price:.2f} deviates {price_dev * Decimal(100):.2f}% from last price {context.last_price:.2f} (max {self.config.price_sanity_pct * Decimal(100):.2f}%)."
                )

        return reasons

    def _check_idempotency(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        reasons: list[str] = []
        if proposal.idempotency_key in context.used_idempotency_keys:
            reasons.append(f"Duplicate idempotency key '{proposal.idempotency_key}' detected.")
        return reasons

    def _check_approvals(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        reasons: list[str] = []
        # C3 & B3 & Review 3 N4: Cryptographic / HMAC owner approval verification for LIVE_WITH_APPROVAL
        if context.mode == "LIVE_WITH_APPROVAL":
            expected_secret = (
                os.environ.get("AEGIS_APPROVAL_SECRET")
                or os.environ.get("AEGIS_OWNER_SECRET")
                or os.environ.get("AEGIS_OWNER_TOKEN")
            )
            ed25519_pubkey_hex = os.environ.get("AEGIS_APPROVAL_PUBLIC_KEY")

            if not expected_secret and not ed25519_pubkey_hex:
                reasons.append(
                    "Approval credential is not configured (AEGIS_APPROVAL_SECRET or AEGIS_APPROVAL_PUBLIC_KEY required); LIVE_WITH_APPROVAL orders cannot be authorized."
                )
                return reasons

            # Reject raw-secret attempt immediately (Review 3 N4 & Proof 6)
            token = context.approval_token
            if token and expected_secret and hmac.compare_digest(token, expected_secret):
                reasons.append(
                    "Raw owner secret is forbidden as an approval credential. Orders require a signed cryptographic approval token covering order parameters, expiry, and nonce."
                )
                return reasons

            # Extract signature components:
            sig = context.approval_signature
            expires_at = context.approval_expires_at
            nonce = context.approval_nonce

            if token and ":" in token and (not sig or not expires_at or not nonce):
                parts = token.split(":")
                if len(parts) == 3:
                    sig, expires_at, nonce = parts[0], parts[1], parts[2]

            if not sig:
                reasons.append("Missing cryptographic approval signature for LIVE_WITH_APPROVAL order.")
                return reasons

            if not expires_at:
                reasons.append("Missing approval expiry timestamp (expires_at required).")
                return reasons

            if not nonce:
                reasons.append("Missing approval nonce (nonce required).")
                return reasons

            # Check expiry
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt <= context.current_ts:
                    reasons.append(f"Approval signature has expired at {expires_at}.")
                    return reasons
            except (ValueError, TypeError) as e:
                reasons.append(f"Invalid approval expiry format: {e}.")
                return reasons

            # Canonical message over all order parameters:
            tp_str = str(proposal.take_profit) if proposal.take_profit is not None else ""
            canonical_msg = f"{proposal.symbol}:{proposal.side.value}:{proposal.order_type.value}:{proposal.size}:{proposal.price}:{proposal.stop_loss}:{tp_str}:{expires_at}:{nonce}"

            valid = False
            # Verify Ed25519 signature if public key provided
            if ed25519_pubkey_hex:
                try:
                    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                    pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ed25519_pubkey_hex))
                    pubkey.verify(bytes.fromhex(sig), canonical_msg.encode("utf-8"))
                    valid = True
                except Exception:  # noqa: BLE001, S110
                    pass

            # Verify HMAC-SHA256 signature if secret provided
            if not valid and expected_secret:
                computed_canonical = hmac.new(
                    expected_secret.encode("utf-8"),
                    canonical_msg.encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()
                if hmac.compare_digest(sig, computed_canonical):
                    valid = True

            if not valid:
                reasons.append("Cryptographic approval signature verification failed for order parameters.")

        return reasons


def create_order_approval_signature(
    secret: str,
    symbol: str,
    side: str,
    order_type: str,
    size: Decimal | str,
    price: Decimal | str,
    stop_loss: Decimal | str,
    take_profit: Decimal | str | None,
    expires_at: str,
    nonce: str
) -> str:
    """Owner-side signer utility creating canonical HMAC-SHA256 signature over order parameters (N4)."""
    tp_str = str(take_profit) if take_profit is not None else ""
    canonical_msg = f"{symbol}:{side}:{order_type}:{size}:{price}:{stop_loss}:{tp_str}:{expires_at}:{nonce}"
    return hmac.new(
        secret.encode("utf-8"),
        canonical_msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
