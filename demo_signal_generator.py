#!/usr/bin/env python3
"""
Demo Signal Generator - Shows trading signals with demo data
"""

import numpy as np
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
import time

console = Console()

# ============================================================================
# TECHNICAL ANALYSIS INDICATORS
# ============================================================================

class TechnicalAnalysis:
    """Real technical analysis indicators"""

    @staticmethod
    def calculate_rsi(prices, period=14):
        """Calculate RSI using Wilder's smoothing"""
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
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)

    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal_period=9):
        """Calculate MACD"""
        prices = list(prices)
        if len(prices) < slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"

        def ema_series(arr, period):
            arr = list(arr)
            if len(arr) < period:
                return []
            seed = float(np.mean(arr[:period]))
            out = [seed]
            multiplier = 2.0 / (period + 1.0)
            for price in arr[period:]:
                seed = (price - seed) * multiplier + seed
                out.append(seed)
            return out

        fast_ema = ema_series(prices, fast)
        slow_ema = ema_series(prices, slow)

        min_len = min(len(fast_ema), len(slow_ema))
        if min_len == 0:
            return 0.0, 0.0, 0.0, "NEUTRAL"

        macd_series = [f - s for f, s in zip(fast_ema[-min_len:], slow_ema[-min_len:])]
        macd_line_last = macd_series[-1]

        if len(macd_series) < signal_period:
            signal_line = np.mean(macd_series)
        else:
            signal_line = TechnicalAnalysis.calculate_ema(macd_series, period=signal_period)

        histogram = macd_line_last - signal_line

        if histogram > 0:
            signal = "BULLISH"
        elif histogram < 0:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return float(macd_line_last), float(signal_line), float(histogram), signal

    @staticmethod
    def calculate_ema(prices, period=20):
        """Calculate EMA"""
        prices = list(prices)
        n = len(prices)
        if n == 0:
            raise ValueError("Empty price list for EMA")
        if n < period:
            return float(np.mean(prices))

        sma = float(np.mean(prices[:period]))
        multiplier = 2.0 / (period + 1.0)
        ema = sma
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return float(ema)

# ============================================================================
# DEMO DATA GENERATOR
# ============================================================================

def generate_demo_prices(base_price=100.0, num_candles=100, volatility=0.02):
    """Generate demo price data"""
    prices = [base_price]
    for _ in range(num_candles - 1):
        change = np.random.normal(0, volatility * base_price)
        new_price = prices[-1] + change
        prices.append(max(new_price, base_price * 0.5))  # Prevent negative
    return prices

# ============================================================================
# SIGNAL GENERATION
# ============================================================================

def generate_signal_for_asset(asset_name, base_price, volatility):
    """Generate trading signal for an asset"""
    ta = TechnicalAnalysis()
    
    prices = generate_demo_prices(base_price, num_candles=100, volatility=volatility)
    current_price = prices[-1]
    
    # Calculate indicators
    rsi = ta.calculate_rsi(prices, period=14)
    macd_line, macd_signal_line, macd_hist, macd_signal = ta.calculate_macd(prices)
    ema_20 = ta.calculate_ema(prices, period=20)
    
    # Generate signal based on indicators
    signal_strength = 0
    direction = None
    reasons = []
    
    # RSI analysis
    if rsi < 30:
        signal_strength += 25
        direction = "CALL"
        reasons.append(f"RSI Oversold ({rsi:.1f})")
    elif rsi > 70:
        signal_strength += 25
        direction = "PUT"
        reasons.append(f"RSI Overbought ({rsi:.1f})")
    
    # MACD analysis
    if macd_signal == "BULLISH":
        if direction in (None, "CALL"):
            signal_strength += 25
            direction = "CALL"
            reasons.append("MACD Bullish")
    elif macd_signal == "BEARISH":
        if direction in (None, "PUT"):
            signal_strength += 25
            direction = "PUT"
            reasons.append("MACD Bearish")
    
    # EMA trend analysis
    if current_price > ema_20:
        if direction in (None, "CALL"):
            signal_strength += 25
            direction = "CALL"
            reasons.append("Above EMA20")
    else:
        if direction in (None, "PUT"):
            signal_strength += 25
            direction = "PUT"
            reasons.append("Below EMA20")
    
    if direction is None:
        direction = "NEUTRAL"
        signal_strength = 50
    
    return {
        "asset": asset_name,
        "direction": direction,
        "strength": min(100, signal_strength),
        "rsi": rsi,
        "macd": macd_signal,
        "price": current_price,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "reasons": reasons
    }

# ============================================================================
# DISPLAY
# ============================================================================

def print_header():
    header = """
    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║       🚀 DEMO QUOTEX SIGNAL GENERATOR 🚀                      ║
    ║       (Simulated Trading Signals - Educational Only)          ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """
    console.print(header, style="bold cyan")

def create_signal_table(signals):
    table = Table(
        title="🎯 LIVE TRADING SIGNALS (DEMO)",
        box=box.DOUBLE_EDGE,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan"
    )
    table.add_column("Asset", style="cyan", width=12)
    table.add_column("Signal", style="bold", width=12)
    table.add_column("Strength", style="yellow", width=12)
    table.add_column("RSI", style="blue", width=10)
    table.add_column("MACD", style="green", width=12)
    table.add_column("Price", style="white", width=12)
    table.add_column("Time", style="dim", width=10)
    
    for s in signals:
        if s["direction"] == "CALL":
            dir_style = "bold green"
            emoji = "📈"
        elif s["direction"] == "PUT":
            dir_style = "bold red"
            emoji = "📉"
        else:
            dir_style = "yellow"
            emoji = "➡️"
        
        strength_emoji = "🔥" if s["strength"] >= 80 else "⚡" if s["strength"] >= 60 else "💫"
        
        table.add_row(
            s["asset"],
            f"{emoji} [{dir_style}]{s['direction']}[/{dir_style}]",
            f"{strength_emoji} {s['strength']}%",
            f"{s['rsi']:.1f}",
            s["macd"],
            f"{s['price']:.2f}",
            s["timestamp"]
        )
    
    return table

def print_signal_details(signal):
    """Print detailed signal information"""
    details = f"""
[bold]{signal['asset']}[/bold] - [{('bold green' if signal['direction'] == 'CALL' else 'bold red')}]{signal['direction']}[/]

📊 Technical Indicators:
   • RSI: {signal['rsi']:.2f}
   • MACD: {signal['macd']}
   • Current Price: {signal['price']:.2f}
   • Signal Strength: {signal['strength']}%

💡 Reasons:
"""
    for reason in signal['reasons']:
        details += f"   ✓ {reason}\n"
    
    console.print(Panel(details, title="📋 Signal Details", border_style="cyan"))

# ============================================================================
# MAIN
# ============================================================================

async def main():
    console.clear()
    print_header()
    
    # Demo assets with base prices and volatility
    assets = [
        ("EURUSD", 1.0850, 0.015),
        ("GBPUSD", 1.2680, 0.018),
        ("AUDUSD", 0.6550, 0.020),
        ("NZDUSD", 0.6050, 0.018),
        ("USDJPY", 149.50, 0.012),
    ]
    
    console.print("\n[cyan]Generating demo trading signals...[/cyan]\n")
    
    iteration = 0
    while True:
        iteration += 1
        signals = []
        
        for asset_name, base_price, volatility in assets:
            signal = generate_signal_for_asset(asset_name, base_price, volatility)
            signals.append(signal)
        
        # Display
        console.clear()
        print_header()
        
        iteration_info = f"[dim]Update #{iteration} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        console.print(iteration_info)
        console.print()
        
        table = create_signal_table(signals)
        console.print(table)
        
        # Show details of strongest signal
        strongest = max(signals, key=lambda s: s['strength'])
        console.print()
        print_signal_details(strongest)
        
        # Instructions
        console.print("\n[dim]Refreshing every 5 seconds... Press Ctrl+C to exit[/dim]")
        
        try:
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏹️ Signal generator stopped[/bold yellow]")
            break

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
