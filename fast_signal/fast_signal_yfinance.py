#!/usr/bin/env python3

import asyncio
import numpy as np
import yfinance as yf
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box

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
    def calculate_macd(prices, fast=12, slow=26, signal_period=9):
        prices = np.asarray(prices, dtype=float)
        if len(prices) < slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"
        
        fast_ema = np.convolve(prices, np.ones(fast)/fast, mode='valid')  # Simple approx
        slow_ema = np.convolve(prices, np.ones(slow)/slow, mode='valid')
        min_len = min(len(fast_ema), len(slow_ema))
        macd_line = fast_ema[-min_len:] - slow_ema[-min_len:]
        signal_line = np.convolve(macd_line, np.ones(signal_period)/signal_period, mode='valid')
        histogram = macd_line[-len(signal_line):] - signal_line
        
        macd_signal = "BULLISH" if histogram[-1] > 0 else "BEARISH" if histogram[-1] < 0 else "NEUTRAL"
        return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1]), macd_signal

    @staticmethod
    def calculate_bollinger_bands(prices, period=20, std_dev=2):
        prices = np.asarray(prices, dtype=float)
        if len(prices) < period:
            return prices[-1], prices[-1], prices[-1]
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        return float(upper), float(sma), float(lower)

    @staticmethod
    def calculate_stochastic(prices, k_period=14, d_period=3):
        prices = np.asarray(prices, dtype=float)
        if len(prices) < k_period:
            return 50.0, 50.0
        highs = np.maximum.accumulate(prices[-k_period:])
        lows = np.minimum.accumulate(prices[-k_period:])
        k = 100 * (prices[-1] - lows[-1]) / (highs[-1] - lows[-1]) if highs[-1] != lows[-1] else 50.0
        # Simple d as average of k
        d = k  # For simplicity, can improve
        return float(k), float(d)

async def get_live_data(asset="EURUSD=X", minutes=60):
    """Get live data from yfinance."""
    try:
        ticker = yf.Ticker(asset)
        data = ticker.history(period="1d", interval="1m").tail(minutes)
        if data.empty:
            return []
        return data['Close'].tolist()
    except:
        return []

async def generate_signals(asset="EURUSD=X", timeframes=[15, 30, 60]):
    signals = {}
    prices = await get_live_data(asset, 60)
    if not prices:
        for tf in timeframes:
            signals[tf] = {"rsi": 50.0, "price": 0.0, "signal": "NO DATA", "confidence": 0}
        return signals
    
    for tf in timeframes:
        sampled_prices = prices[-tf:] if len(prices) >= tf else prices
        if len(sampled_prices) < 20:  # Need more for indicators
            signals[tf] = {"rsi": 50.0, "price": prices[-1] if prices else 0.0, "signal": "INSUFFICIENT DATA", "confidence": 0}
            continue
        
        current_price = sampled_prices[-1]
        rsi = TechnicalAnalysis.calculate_rsi(sampled_prices, period=14)
        macd_line, macd_signal, macd_hist, macd_dir = TechnicalAnalysis.calculate_macd(sampled_prices)
        upper_bb, sma_bb, lower_bb = TechnicalAnalysis.calculate_bollinger_bands(sampled_prices)
        stoch_k, stoch_d = TechnicalAnalysis.calculate_stochastic(sampled_prices)
        
        # Advanced Signal Logic with Multi-Indicator Confirmation
        buy_score = 0
        sell_score = 0
        
        # RSI
        if rsi < 30:
            buy_score += 30
        elif rsi > 70:
            sell_score += 30
        
        # MACD
        if macd_dir == "BULLISH":
            buy_score += 25
        elif macd_dir == "BEARISH":
            sell_score += 25
        
        # Bollinger Bands
        if current_price < lower_bb:
            buy_score += 20
        elif current_price > upper_bb:
            sell_score += 20
        
        # Stochastic
        if stoch_k < 20:
            buy_score += 15
        elif stoch_k > 80:
            sell_score += 15
        
        # Final Decision
        if buy_score >= 50:
            signal = "STRONG BUY"
            confidence = min(100, buy_score)
        elif sell_score >= 50:
            signal = "STRONG SELL"
            confidence = min(100, sell_score)
        elif buy_score >= 30:
            signal = "BUY"
            confidence = buy_score
        elif sell_score >= 30:
            signal = "SELL"
            confidence = sell_score
        else:
            signal = "NEUTRAL"
            confidence = 0
        
        signals[tf] = {
            "rsi": rsi,
            "price": current_price,
            "signal": signal,
            "confidence": confidence,
            "macd": macd_dir,
            "bb_position": "BELOW" if current_price < lower_bb else "ABOVE" if current_price > upper_bb else "MIDDLE",
            "stoch": stoch_k
        }
    
    return signals


def smooth_signals(asset_name, signals, history, min_stable=2):
    """Mark each timeframe as stable only after it holds at least min_stable consecutive cycles."""
    for tf, data in signals.items():
        key = (asset_name, tf)
        previous = history.get(key)
        if previous and previous.get("signal") == data.get("signal"):
            count = previous.get("count", 0) + 1
        else:
            count = 1

        history[key] = {"signal": data.get("signal"), "count": count}
        data["stable"] = "STABLE" if count >= min_stable else "UNSTABLE"

    return signals


async def display_signals(signals, asset_name="Unknown"):
    table = Table(title=f"📊 {asset_name} - High-Accuracy Signals", box=box.DOUBLE_EDGE, style="cyan")
    table.add_column("Asset", style="bold cyan", justify="center")
    table.add_column("Time", style="white", justify="center")
    table.add_column("Timeframe", style="cyan", justify="center")
    table.add_column("RSI", style="magenta", justify="right")
    table.add_column("Price", style="white", justify="right")
    table.add_column("MACD", style="blue", justify="center")
    table.add_column("BB Pos", style="green", justify="center")
    table.add_column("Stoch K", style="yellow", justify="right")
    table.add_column("Signal", style="bold", justify="center")
    table.add_column("Conf%", style="red", justify="right")
    table.add_column("Status", style="yellow", justify="center")
    table.add_column("Action", style="bold", justify="center")
    
    for tf, data in signals.items():
        tf_str = f"{tf}s" if tf < 60 else f"{tf//60}m"
        rsi = f"{data['rsi']:.1f}"
        price = f"{data['price']:.5f}"
        macd = data.get('macd', 'N/A')
        bb_pos = data.get('bb_position', 'N/A')
        stoch = f"{data.get('stoch', 50):.1f}"
        signal = data['signal']
        confidence = data.get('confidence', 0)
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = data.get('stable', 'UNSTABLE')
        
        # Signal color coding
        if "STRONG BUY" in signal:
            signal_style = "[bold green]STRONG BUY[/bold green]"
            action = "[bold green]→ CALL ✓[/bold green]"
        elif "STRONG SELL" in signal:
            signal_style = "[bold red]STRONG SELL[/bold red]"
            action = "[bold red]→ PUT ✓[/bold red]"
        elif signal == "BUY":
            signal_style = "[green]BUY[/green]"
            action = "[green]CALL[/green]"
        elif signal == "SELL":
            signal_style = "[red]SELL[/red]"
            action = "[red]PUT[/red]"
        else:
            signal_style = "[yellow]NEUTRAL[/yellow]"
            action = "[dim]WAIT[/dim]"
        
        status_style = "[green]STABLE[/green]" if status == "STABLE" else "[yellow]UNSTABLE[/yellow]"
        table.add_row(asset_name, timestamp, tf_str, rsi, price, macd, bb_pos, stoch, signal_style, f"{confidence}%", status_style, action)
    
    console.print(table)

async def display_asset_recommendation(asset_name, signals):
    """Show recommendation summary for the asset."""
    best_signal = max(signals.values(), key=lambda x: x.get('confidence', 0))
    
    if best_signal['confidence'] >= 70:
        recommendation = f"[bold green]✅ STRONG: {best_signal['signal']}[/bold green]"
        action = "→ CALL" if "BUY" in best_signal['signal'] else "→ PUT"
        action_style = "[bold green]" + action + "[/bold green]"
    elif best_signal['confidence'] >= 50:
        recommendation = f"[bold yellow]⚠️ MODERATE: {best_signal['signal']}[/bold yellow]"
        action = "→ CALL" if "BUY" in best_signal['signal'] else "→ PUT"
        action_style = "[bold yellow]" + action + "[/bold yellow]"
    else:
        recommendation = "[dim]🔔 WAIT[/dim]"
        action = "NONE"
        action_style = "[dim]NONE[/dim]"
    
    console.print(f"{recommendation} | Confidence: {best_signal['confidence']}% | Action: {action_style}\n")

async def main():
    console.clear()
    console.print("[bold cyan]🚀 Starting High-Accuracy Multi-Asset Signal Generator (yfinance)...[/bold cyan]\n")
    
    # Multiple assets
    assets = {
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "JPY=X": "USD/JPY",
        "BTC-USD": "BTC/USD"
    }
    
    # Note: USD/BDT may not be available on yfinance, using closest alternatives
    timeframes = [15, 30, 60]  # 15s, 30s, 1m

    signal_history = {}
    
    while True:
        try:
            console.clear()
            console.print(f"[bold cyan]🚀 Multi-Asset High-Accuracy Signals - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold cyan]\n")
            
            for symbol, asset_name in assets.items():
                signals = await generate_signals(symbol, timeframes)
                signals = smooth_signals(asset_name, signals, signal_history, min_stable=2)
                await display_signals(signals, asset_name)
                await display_asset_recommendation(asset_name, signals)
            
            console.print(f"\n[dim]Refreshing in 1 second... (Near Zero Delay)[/dim]")
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏹️ Stopped by user.[/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]⚠️ Error: {e}[/red]")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())