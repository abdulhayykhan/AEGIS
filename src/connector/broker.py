import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.gate.models import OrderSide, OrderType


class BrokerOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: uuid.UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    size: Decimal
    status: str  # "SUBMITTED", "FILLED", "CANCELLED"
    created_at: datetime


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    size: Decimal
    avg_price: Decimal


class PaperBroker:
    """Deterministic Paper Broker simulator for testnet / paper trading.
    
    Maintains account equity, cash, open positions, and order book simulation.
    """

    def __init__(self, initial_cash: Decimal = Decimal("10000.00")) -> None:
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: dict[uuid.UUID, BrokerOrder] = {}
        self.trade_history: list[dict[str, Any]] = []
        self.realized_pnl: Decimal = Decimal("0.00")
        self.total_fees_paid: Decimal = Decimal("0.00")

    def get_account_summary(self, mark_prices: dict[str, Decimal]) -> dict[str, Any]:
        unrealized_pnl = Decimal("0.00")
        position_notionals = Decimal("0.00")

        positions_dict = {}
        for sym, pos in self.positions.items():
            mark = mark_prices.get(sym, pos.avg_price)
            notional = pos.size * mark
            pnl = (mark - pos.avg_price) * pos.size
            unrealized_pnl += pnl
            position_notionals += notional
            positions_dict[sym] = {
                "size": str(pos.size),
                "avg_price": str(pos.avg_price),
                "notional": str(notional),
                "unrealized_pnl": str(pnl)
            }

        equity = self.cash + position_notionals
        return {
            "cash": str(self.cash),
            "equity": str(equity),
            "unrealized_pnl": str(unrealized_pnl),
            "positions": positions_dict
        }

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        price: Decimal,
        size: Decimal,
        mark_price: Decimal,
        fee_rate: Decimal = Decimal("0.0010")  # 0.10% taker fee per PRD Section 11
    ) -> BrokerOrder:
        order_id = uuid.uuid4()
        now = datetime.now(UTC)

        # Immediate fill simulation for limit orders at or better than mark price
        will_fill = (side == OrderSide.BUY and price >= mark_price) or (side == OrderSide.SELL and price <= mark_price)
        status = "FILLED" if will_fill else "SUBMITTED"

        if status == "FILLED":
            cost = price * size
            fee = cost * fee_rate

            if side == OrderSide.BUY:
                self.cash -= (cost + fee)
                existing_pos = self.positions.get(symbol)
                if existing_pos:
                    new_size = existing_pos.size + size
                    new_avg = ((existing_pos.avg_price * existing_pos.size) + (price * size)) / new_size
                    self.positions[symbol] = Position(symbol=symbol, size=new_size, avg_price=new_avg)
                else:
                    self.positions[symbol] = Position(symbol=symbol, size=size, avg_price=price)
            elif side == OrderSide.SELL:
                existing_pos = self.positions.get(symbol)
                if not existing_pos or existing_pos.size < size:
                    held = existing_pos.size if existing_pos else Decimal(0)
                    raise ValueError(
                        f"Cannot sell without position: held {held} of '{symbol}', attempted to sell {size}. Shorting disabled."
                    )
                self.cash += (cost - fee)
                closed_size = size
                trade_pnl = (price - existing_pos.avg_price) * closed_size
                self.realized_pnl += trade_pnl
                rem_size = existing_pos.size - size
                if rem_size <= Decimal(0):
                    self.positions.pop(symbol, None)
                else:
                    self.positions[symbol] = Position(symbol=symbol, size=rem_size, avg_price=existing_pos.avg_price)

            self.total_fees_paid += fee
            self.trade_history.append({
                "trade_id": str(uuid.uuid4()),
                "order_id": str(order_id),
                "symbol": symbol,
                "side": side.value,
                "price": str(price),
                "size": str(size),
                "fee": str(fee),
                "ts": now.isoformat()
            })

        order = BrokerOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            size=size,
            status=status,
            created_at=now
        )
        self.orders[order_id] = order
        return order

    def cancel_all_open_orders(self) -> int:
        """Cancel all active SUBMITTED orders (e.g. on kill switch engagement)."""
        count = 0
        for o_id, order in list(self.orders.items()):
            if order.status == "SUBMITTED":
                self.orders[o_id] = BrokerOrder(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    price=order.price,
                    size=order.size,
                    status="CANCELLED",
                    created_at=order.created_at
                )
                count += 1
        return count

    def cancel_order(self, order_id: uuid.UUID) -> bool:
        if order_id in self.orders and self.orders[order_id].status == "SUBMITTED":
            old_order = self.orders[order_id]
            self.orders[order_id] = BrokerOrder(
                order_id=old_order.order_id,
                symbol=old_order.symbol,
                side=old_order.side,
                order_type=old_order.order_type,
                price=old_order.price,
                size=old_order.size,
                status="CANCELLED",
                created_at=old_order.created_at
            )
            return True
        return False

    def get_open_orders(self) -> list[dict[str, Any]]:
        return [
            {
                "order_id": str(o.order_id),
                "symbol": o.symbol,
                "side": o.side.value,
                "order_type": o.order_type.value,
                "price": str(o.price),
                "size": str(o.size),
                "status": o.status,
                "created_at": o.created_at.isoformat()
            }
            for o in self.orders.values()
            if o.status == "SUBMITTED"
        ]
