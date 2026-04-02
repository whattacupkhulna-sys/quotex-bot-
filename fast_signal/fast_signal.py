#!/usr/bin/env python3

import os
import sys
import time
import numpy as np
import asyncio
from rich.console import Console

# পাইথনকে ফোল্ডারের রাস্তা চিনেয়ে দেওয়া হচ্ছে
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..', 'API-Quotex-main'))
sys.path.append(parent_dir)

try:
    from api_quotex.client import AsyncQuotexClient as Quotex
    from api_quotex.login import get_ssid
except ImportError:
    print("❌ Error: 'api_quotex' still not found! Please check the folder name.")
    exit()

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


async def main():
    console.clear()
    console.print("[cyan]🚀 Starting ZERO-DELAY Quotex Signal Generator...[/cyan]")
    
    # Get SSID
    console.print("[yellow]🔄 Getting session ID...[/yellow]")
    success, session_data = await get_ssid(email="abcd34563489@gmail.com", password="{ TtT<Tisha343433}", is_demo=True)
    if not success:
        console.print("[bold red]❌ Failed to get session ID! Check credentials.[/bold red]")
        return
    ssid = session_data.get("ssid") or session_data.get("token")
    if not ssid:
        console.print("[bold red]❌ No SSID or token found![/bold red]")
        return
    
    # Quotex ক্লায়েন্ট তৈরি
    client = Quotex(ssid=ssid, is_demo=True)
    
    console.print("[yellow]🔄 Connecting to Quotex WebSocket...[/yellow]")
    
    # কানেক্ট করার চেষ্টা
    connected = await client.connect()
    
    # কানেকশন স্ট্যাটাস চেক
    if not connected:
        console.print("[bold red]❌ Connection Failed! সেশন আইডি বা ইন্টারনেট চেক করুন।[/bold red]")
        return
        
    console.print("[bold green]✅ Connected Successfully! (সরাসরি ব্রোকার থেকে লাইভ ডেটা আসছে)[/bold green]\n")

    asset = "EURUSD_otc"
    ta = TechnicalAnalysis()

    console.print(f"[dim]Scanning {asset} for perfect entry... (Press Ctrl+C to stop)[/dim]\n")

    while True:
        try:
            candles = await client.get_candles(asset, 60)

            prices = []
            if candles:
                if isinstance(candles, dict) and 'data' in candles:
                    prices = [c['close'] for c in candles['data'] if 'close' in c]
                elif isinstance(candles, list):
                    prices = [c['close'] if isinstance(c, dict) and 'close' in c else c for c in candles]

            if len(prices) >= 20:
                current_price = prices[-1]
                rsi = ta.calculate_rsi(prices)
                ema_20 = ta.calculate_ema(prices)

                if rsi < 30 and current_price > ema_20:
                    console.print(f"\n🔥 [bold green]BUY NOW (CALL)[/bold green] | 📈 Asset: {asset} | RSI: {rsi:.1f} | Price: {current_price}")
                elif rsi > 70 and current_price < ema_20:
                    console.print(f"\n🔥 [bold red]SELL NOW (PUT)[/bold red] | 📉 Asset: {asset} | RSI: {rsi:.1f} | Price: {current_price}")
                else:
                    print(f"⏳ Waiting... {asset} | Current RSI: {rsi:.1f} | Live Price: {current_price:.5f}", end="\r")
            else:
                console.print("[dim]⏳ Waiting for enough candle data (20 required)...[/dim]")

            time.sleep(1)

        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏹️ Stopped by user.[/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]⚠️ Error fetching data: {e}[/red]")
            time.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
