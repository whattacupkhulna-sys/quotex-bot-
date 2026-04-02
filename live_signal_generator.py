#!/usr/bin/env python3
"""
Live signal generator using Yahoo Finance (yfinance)
"""

import numpy as np
import yfinance as yf
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
import asyncio

console = Console()

class TechnicalAnalysis:
    @staticmethod
    def calculate_rsi(prices, period=14):
        prices = np.asarray(prices, dtype=float)
        if prices.size < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def calculate_ema(prices, period=20):
        prices = list(prices)
        if len(prices) == 0:
            return 0.0
        if len(prices) < period:
            return float(np.mean(prices))

        sma = float(np.mean(prices[:period]))
        multiplier = 2.0 / (period + 1.0)
        ema = sma
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return float(ema)


def get_real_market_data(asset_symbol, minutes=60):
    """Fetch latest close prices from Yahoo Finance."""
    try:
        ticker = yf.Ticker(asset_symbol)
        history = ticker.history(period="1d", interval="1m")
        if history.empty:
            return []

        closes = history['Close'].dropna().tolist()
        if len(closes) < minutes:
            # fallback to whatever we have
            return closes

        return closes[-minutes:]
    except Exception as exc:
        console.print(f"[red]Failed to get data for {asset_symbol}: {exc}[/red]")
        return []


def generate_live_signal(asset_name, display_name):
    prices = get_real_market_data(asset_name, minutes=60)
    if not prices:
        return None

    ta = TechnicalAnalysis()
    current_price = prices[-1]
    rsi = ta.calculate_rsi(prices)
    ema_20 = ta.calculate_ema(prices)

    direction = "NEUTRAL"
    strength = 50
    reasons = []

    if rsi < 35 and current_price > ema_20:
        direction, strength = "CALL", 85
        reasons.append(f"RSI Oversold ({rsi:.1f}) + Trend Up")
    elif rsi > 65 and current_price < ema_20:
        direction, strength = "PUT", 85
        reasons.append(f"RSI Overbought ({rsi:.1f}) + Trend Down")
    elif rsi < 30:
        direction, strength = "CALL", 70
        reasons.append("RSI Critical Oversold")
    elif rsi > 70:
        direction, strength = "PUT", 70
        reasons.append("RSI Critical Overbought")

    return {
        "asset": display_name,
        "direction": direction,
        "strength": strength,
        "rsi": rsi,
        "price": current_price,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "reasons": reasons,
    }


async def main():
    assets = [
        ("EURUSD=X", "EUR/USD"),
        ("GBPUSD=X", "GBP/USD"),
        ("JPY=X", "USD/JPY"),
        ("BTC-USD", "BTC/USD"),
    ]

    while True:
        console.clear()
        console.print(Panel("🚀 LIVE MARKET SIGNALS (YFINANCE) 🚀", style="bold cyan", expand=False))

        table = Table(title=f"Last Update: {datetime.now().strftime('%H:%M:%S')}", box=box.DOUBLE_EDGE)
        table.add_column("Asset", style="cyan")
        table.add_column("Signal", style="bold")
        table.add_column("Strength", style="yellow")
        table.add_column("RSI", style="magenta")
        table.add_column("Price", style="white")

        signals = []
        for symbol, name in assets:
            sig = generate_live_signal(symbol, name)
            if sig:
                signals.append(sig)
                style = "bold green" if sig['direction'] == "CALL" else "bold red" if sig['direction'] == "PUT" else "white"
                table.add_row(sig['asset'], f"[{style}]{sig['direction']}[/]", f"{sig['strength']}%", f"{sig['rsi']:.1f}", f"{sig['price']:.4f}")

        console.print(table)

        if signals:
            strongest = max(signals, key=lambda x: x['strength'])
            if strongest['reasons']:
                console.print(Panel(
                    f"🎯 Best Opportunity: {strongest['asset']} ({strongest['direction']})\n"
                    f"💡 Why: {', '.join(strongest['reasons'])}",
                    title="Recommendation",
                    border_style="green",
                ))

        console.print("\n[dim]Refreshing in 30 seconds... (Yahoo Finance rate limiting may apply)[/dim]")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
