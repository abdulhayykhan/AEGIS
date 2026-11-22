"""Tests for historical market data loader and public exchange fetcher.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
"""

from decimal import Decimal
from pathlib import Path

from src.signals.data_loader import HistoricalDataLoader
from src.signals.models import Bar


def test_load_bars_from_json(tmp_path: Path) -> None:
    sample_json = tmp_path / "test_bars.json"
    sample_json.write_text(
        """[
            {"ts": 1700000000, "open": "35000.0", "high": "35500.0", "low": "34800.0", "close": "35200.0", "volume": "100.5"},
            {"ts": 1700086400, "open": "35200.0", "high": "36000.0", "low": "35100.0", "close": "35900.0", "volume": "150.2"}
        ]""",
        encoding="utf-8"
    )

    loader = HistoricalDataLoader(data_dir=tmp_path)
    bars = loader.load_bars_from_file(sample_json)

    assert len(bars) == 2
    assert isinstance(bars[0], Bar)
    assert bars[0].close == Decimal("35200.0")
    assert bars[1].close == Decimal("35900.0")
    assert bars[1].volume == Decimal("150.2")


def test_parse_binance_kline() -> None:
    loader = HistoricalDataLoader()
    kline = [
        1700000000000,  # 0: Open time in ms
        "36000.50",     # 1: Open
        "36500.00",     # 2: High
        "35800.00",     # 3: Low
        "36200.00",     # 4: Close
        "125.750",      # 5: Volume
        1700086399999,  # 6: Close time
    ]
    bar = loader.parse_kline(kline)
    assert bar.ts == 1700000000
    assert bar.open == Decimal("36000.50")
    assert bar.high == Decimal("36500.00")
    assert bar.low == Decimal("35800.00")
    assert bar.close == Decimal("36200.00")
    assert bar.volume == Decimal("125.750")
