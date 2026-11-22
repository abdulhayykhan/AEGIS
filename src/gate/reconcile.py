from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PositionState(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    size: Decimal
    avg_price: Decimal


class AccountState(BaseModel):
    model_config = ConfigDict(frozen=True)

    equity: Decimal
    cash: Decimal
    positions: dict[str, PositionState]


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    match: bool
    diffs: list[str]


def reconcile_states(db_state: AccountState, broker_state: AccountState) -> ReconciliationResult:
    """Compare database state against broker state down to the cent / minor unit."""
    diffs: list[str] = []

    # 1. Compare cash balances
    if db_state.cash != broker_state.cash:
        diffs.append(
            f"Cash mismatch: DB={db_state.cash:.2f} USDT vs Broker={broker_state.cash:.2f} USDT (diff: {db_state.cash - broker_state.cash:.2f})"
        )

    # 2. Compare equity
    if db_state.equity != broker_state.equity:
        diffs.append(
            f"Equity mismatch: DB={db_state.equity:.2f} USDT vs Broker={broker_state.equity:.2f} USDT (diff: {db_state.equity - broker_state.equity:.2f})"
        )

    # 3. Compare open positions
    all_symbols = set(db_state.positions.keys()).union(set(broker_state.positions.keys()))
    for sym in all_symbols:
        db_pos = db_state.positions.get(sym)
        broker_pos = broker_state.positions.get(sym)

        if db_pos is None and broker_pos is not None:
            diffs.append(f"Missing position in DB: Broker holds {broker_pos.size} of {sym}")
        elif db_pos is not None and broker_pos is None:
            diffs.append(f"Missing position in Broker: DB records {db_pos.size} of {sym}")
        elif db_pos is not None and broker_pos is not None and db_pos.size != broker_pos.size:
            diffs.append(
                f"Size mismatch for {sym}: DB={db_pos.size} vs Broker={broker_pos.size}"
            )


    return ReconciliationResult(
        match=len(diffs) == 0,
        diffs=diffs
    )
