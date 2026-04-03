#!/usr/bin/env python3

import sys
import os
import asyncio
import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box

# Path Setup: Automatically add API-Quotex-main to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_path = os.path.abspath(os.path.join(current_dir, '..', 'API-Quotex-main'))
if api_path not in sys.path:
    sys.path.append(api_path)

try:
    from api_quotex.client import AsyncQuotexClient
    from api_quotex.login import get_ssid
except ImportError as e:
    print(f"❌ Error importing api_quotex: {e}")
    print("Make sure API-Quotex-main folder is in the parent directory.")
    exit(1)

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


async def get_client():
    """Authenticate and return AsyncQuotexClient with ssid."""
    email = "abcd34563489@gmail.com"
    password = "{TtT<Tisha343433}"
    
    console.print("[yellow]🔄 Authenticating with Quotex...[/yellow]")
    success, session_data = await get_ssid(email=email, password=password, is_demo=True)
    if not success:
        console.print("[bold red]❌ Authentication failed! Check credentials.[/bold red]")
        return None
    
    ssid = session_data.get("ssid") or session_data.get("token")
    if not ssid:
        console.print("[bold red]❌ No SSID found![/bold red]")
        return None
    
    client = AsyncQuotexClient(ssid=ssid, is_demo=True)
    console.print("[green]✅ Client created with SSID.[/green]")
    return client


async def generate_signals(client, asset="EURUSD_otc", timeframes=[15, 30, 60]):
    """Generate signals for multiple timeframes."""
    signals = {}
    for tf in timeframes:
        try:
            # Get candles (assuming tf in seconds, adjust if needed)
            candles = await client.get_candles(asset, tf * 60)  # Convert to minutes if API expects minutes
            if not candles:
                signals[tf] = {"rsi": 50.0, "price": 0.0, "signal": "NEUTRAL"}
                continue
            
            prices = []
            if isinstance(candles, dict) and 'data' in candles:
                prices = [c['close'] for c in candles['data'] if 'close' in c]
            elif isinstance(candles, list):
                prices = [c['close'] if isinstance(c, dict) and 'close' in c else c for c in candles]
            
            if len(prices) < 15:
                signals[tf] = {"rsi": 50.0, "price": 0.0, "signal": "NEUTRAL"}
                continue
            
            current_price = prices[-1]
            rsi = TechnicalAnalysis.calculate_rsi(prices, period=14)
            
            if rsi < 25:
                signal = "BUY"
            elif rsi > 75:
                signal = "SELL"
            else:
                signal = "NEUTRAL"
            
            signals[tf] = {"rsi": rsi, "price": current_price, "signal": signal}
        
        except Exception as e:
            console.print(f"[red]⚠️ Error for {tf}s: {e}[/red]")
            signals[tf] = {"rsi": 50.0, "price": 0.0, "signal": "ERROR"}
    
    return signals


async def display_signals(signals):
    """Display signals in a clean table."""
    table = Table(title="🚀 Zero-Delay Quotex Signals (EURUSD_otc)", box=box.DOUBLE_EDGE)
    table.add_column("Timeframe", style="cyan", justify="center")
    table.add_column("RSI", style="magenta", justify="right")
    table.add_column("Price", style="white", justify="right")
    table.add_column("Signal", style="bold", justify="center")
    
    for tf, data in signals.items():
        tf_str = f"{tf}s" if tf < 60 else f"{tf//60}m"
        rsi = f"{data['rsi']:.1f}"
        price = f"{data['price']:.5f}"
        signal = data['signal']
        if signal == "BUY":
            signal_style = "[bold green]BUY[/bold green]"
        elif signal == "SELL":
            signal_style = "[bold red]SELL[/bold red]"
        else:
            signal_style = "[yellow]NEUTRAL[/yellow]"
        table.add_row(tf_str, rsi, price, signal_style)
    
    console.print(table)


async def main():
    console.clear()
    console.print("[bold cyan]🚀 Starting Zero-Delay High-Accuracy Signal Generator...[/bold cyan]\n")
    
    client = await get_client()
    if not client:
        return
    
    console.print("[yellow]🔄 Connecting to Quotex WebSocket...[/yellow]")
    connected = await client.connect()
    if not connected:
        console.print("[bold red]❌ Connection failed![/bold red]")
        return
    
    console.print("[bold green]✅ Connected! Starting real-time signal generation...[/bold green]\n")
    
    asset = "EURUSD_otc"
    timeframes = [15, 30, 60]  # 15s, 30s, 1m
    
    while True:
        try:
            signals = await generate_signals(client, asset, timeframes)
            await display_signals(signals)
            console.print("\n[dim]Refreshing in 1 second... (Zero Delay)[/dim]")
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏹️ Stopped by user.[/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]⚠️ Error: {e}[/red]")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
