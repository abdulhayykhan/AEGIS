"""AEGIS Historical Market Data Ingestion & Public Exchange Loader.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Section 5 Step 3.3 & Finding H5)
- TauricResearch / TradingAgents: Multi-asset historical OHLCV normalization
"""

import json
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.signals.models import Bar


class HistoricalDataLoader:
    """Loads and normalizes real historical bar data from local fixtures or public exchange APIs."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or (Path(__file__).parent.parent.parent / "backtest" / "historical_bars")

    def parse_kline(self, kline: list[Any]) -> Bar:
        """Parse raw exchange kline array [open_time_ms, open, high, low, close, volume, ...] into Bar."""
        ts_ms = int(kline[0])
        ts = int(ts_ms // 1000)
        return Bar(
            ts=ts,
            open=Decimal(str(kline[1])),
            high=Decimal(str(kline[2])),
            low=Decimal(str(kline[3])),
            close=Decimal(str(kline[4])),
            volume=Decimal(str(kline[5]))
        )

    def load_bars_from_file(self, file_path: Path) -> list[Bar]:
        """Load and parse pre-stored JSON bar records."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        bars: list[Bar] = []
        for item in raw_data:
            if isinstance(item, list):
                bars.append(self.parse_kline(item))
            elif isinstance(item, dict):
                bars.append(Bar(
                    ts=int(item["ts"]),
                    open=Decimal(str(item["open"])),
                    high=Decimal(str(item["high"])),
                    low=Decimal(str(item["low"])),
                    close=Decimal(str(item["close"])),
                    volume=Decimal(str(item["volume"]))
                ))
        return bars

    def fetch_binance_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1d",
        limit: int = 1000
    ) -> list[Bar]:
        """Fetch real public historical klines from Binance public REST API (no auth required)."""
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AEGIS-DataFetcher/1.0 (Abdul Hayy Khan)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        return [self.parse_kline(item) for item in data]

    def save_bars_to_json(self, bars: list[Bar], output_path: Path) -> None:
        """Save normalized bar collection to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [
            {
                "ts": b.ts,
                "open": str(b.open),
                "high": str(b.high),
                "low": str(b.low),
                "close": str(b.close),
                "volume": str(b.volume)
            }
            for b in bars
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2)

    def get_or_fetch_bars(self, symbol: str = "BTC/USDT", interval: str = "1d") -> list[Bar]:
        """Retrieve cached bars from backtest/historical_bars/ or fetch live if not cached."""
        clean_symbol = symbol.replace("/", "_")
        cache_file = self.data_dir / f"{clean_symbol}_{interval}.json"

        if cache_file.exists():
            return self.load_bars_from_file(cache_file)

        binance_symbol = symbol.replace("/", "")
        bars = self.fetch_binance_klines(symbol=binance_symbol, interval=interval, limit=1000)
        self.save_bars_to_json(bars, cache_file)
        return bars
