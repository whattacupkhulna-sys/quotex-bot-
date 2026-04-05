#!/usr/bin/env python3

import asyncio
import os
import sys
from pathlib import Path

import numpy as np
import yfinance as yf
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

# Prefer Quotex live candles when available; fallback to yfinance otherwise.
DATA_SOURCE = "QUOTEX"
QUOTEX_ROOT = Path(__file__).resolve().parents[1] / "API-Quotex-main"
QUOTEX_AVAILABLE = False
AsyncQuotexClient = None
get_ssid = None

if QUOTEX_ROOT.exists():
    sys.path.insert(0, str(QUOTEX_ROOT))
    try:
        from api_quotex.client import AsyncQuotexClient
        from api_quotex.login import get_ssid
        QUOTEX_AVAILABLE = True
    except Exception:
        QUOTEX_AVAILABLE = False

if not QUOTEX_AVAILABLE:
    DATA_SOURCE = "YFINANCE"

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

    @staticmethod
    def calculate_trend_strength(prices, short=5, long=20):
        prices = np.asarray(prices, dtype=float)
        if len(prices) < long:
            return 0.0
        short_ma = np.mean(prices[-short:])
        long_ma = np.mean(prices[-long:])
        return float((short_ma - long_ma) / long_ma * 100.0)

    @staticmethod
    def ai_predict_signal(rsi, macd_dir, bb_position, stoch_k, trend_strength):
        score = 0.0
        score += (50.0 - rsi) * 0.4
        score += 10.0 if macd_dir == "BULLISH" else -10.0 if macd_dir == "BEARISH" else 0.0
        score += 7.0 if bb_position == "BELOW" else -7.0 if bb_position == "ABOVE" else 0.0
        score += (50.0 - stoch_k) * 0.2
        score += trend_strength * 0.5
        ai_direction = "BUY" if score > 15 else "SELL" if score < -15 else "NEUTRAL"
        return float(score), ai_direction

QUOTEX_ASSET_MAP = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "JPY=X": "USDJPY",
    "BTC-USD": "BTCUSD_otc",
}

class QuotexDataSource:
    def __init__(self):
        self.client = None
        self.connected = False

    async def connect(self):
        if not QUOTEX_AVAILABLE:
            return False
        try:
            success, session_data = await get_ssid()
            if not success or not session_data:
                return False
            ssid = session_data.get("ssid")
            if not ssid:
                return False
            self.client = AsyncQuotexClient(
                ssid=ssid,
                is_demo=session_data.get("is_demo", True),
                persistent_connection=False,
                enable_logging=False,
            )
            self.connected = await self.client.connect()
            return self.connected
        except Exception:
            return False

    def map_asset(self, asset):
        return QUOTEX_ASSET_MAP.get(asset, asset.replace("=X", "").replace("-USD", "USD").replace("/", "").upper())

    async def get_prices(self, asset, minutes=120):
        if not self.client or not self.connected:
            return []
        try:
            quotex_symbol = self.map_asset(asset)
            df = await self.client.get_candles_dataframe(quotex_symbol, "1m", count=minutes)
            if df.empty:
                return []
            return df["close"].tolist()
        except Exception:
            return []

    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None
            self.connected = False

quotex_source = QuotexDataSource()

async def get_live_data(asset="EURUSD=X", minutes=60):
    """Fetch live close prices from Quotex or yfinance."""
    if DATA_SOURCE == "QUOTEX" and QUOTEX_AVAILABLE:
        prices = await quotex_source.get_prices(asset, minutes)
        if prices:
            return prices
        # Fallback if Quotex data is unavailable.
    try:
        ticker = yf.Ticker(asset)
        data = ticker.history(period="1d", interval="1m").tail(minutes)
        if data.empty:
            return []
        return data['Close'].tolist()
    except Exception:
        return []

async def generate_signals(asset="EURUSD=X", timeframes=[60]):
    signals = {}
    prices = await get_live_data(asset, 120)
    if not prices:
        for tf in timeframes:
            signals[tf] = {"rsi": 50.0, "price": 0.0, "signal": "NO DATA", "confidence": 0, "ai_signal": "NEUTRAL", "ai_score": 0.0}
        return signals
    
    for tf in timeframes:
        sampled_prices = prices[-tf:] if len(prices) >= tf else prices
        if len(sampled_prices) < 20:  # Need more for indicators
            signals[tf] = {
                "rsi": 50.0,
                "price": prices[-1] if prices else 0.0,
                "signal": "INSUFFICIENT DATA",
                "confidence": 0,
                "ai_signal": "NEUTRAL",
                "ai_score": 0.0,
                "macd": "N/A",
                "bb_position": "N/A",
                "stoch": 50.0,
            }
            continue
        
        current_price = sampled_prices[-1]
        rsi = TechnicalAnalysis.calculate_rsi(sampled_prices, period=14)
        macd_line, macd_signal, macd_hist, macd_dir = TechnicalAnalysis.calculate_macd(sampled_prices)
        upper_bb, sma_bb, lower_bb = TechnicalAnalysis.calculate_bollinger_bands(sampled_prices)
        stoch_k, stoch_d = TechnicalAnalysis.calculate_stochastic(sampled_prices)
        trend_strength = TechnicalAnalysis.calculate_trend_strength(sampled_prices)
        ai_score, ai_signal = TechnicalAnalysis.ai_predict_signal(rsi, macd_dir, "BELOW" if current_price < lower_bb else "ABOVE" if current_price > upper_bb else "MIDDLE", stoch_k, trend_strength)
        
        # Strong multi-indicator scoring
        buy_score = 0
        sell_score = 0
        
        if rsi < 35:
            buy_score += 30
        elif rsi > 65:
            sell_score += 30
        
        if macd_dir == "BULLISH":
            buy_score += 25
        elif macd_dir == "BEARISH":
            sell_score += 25
        
        if current_price < lower_bb:
            buy_score += 20
        elif current_price > upper_bb:
            sell_score += 20
        
        if stoch_k < 25:
            buy_score += 15
        elif stoch_k > 75:
            sell_score += 15
        
        if trend_strength > 0.2:
            buy_score += min(15, int(trend_strength * 2))
        elif trend_strength < -0.2:
            sell_score += min(15, int(-trend_strength * 2))
        
        if ai_signal == "BUY":
            buy_score += 10
        elif ai_signal == "SELL":
            sell_score += 10
        
        if buy_score >= sell_score + 20:
            signal = "STRONG BUY"
            confidence = min(100, buy_score)
        elif sell_score >= buy_score + 20:
            signal = "STRONG SELL"
            confidence = min(100, sell_score)
        elif buy_score > sell_score:
            signal = "BUY"
            confidence = min(100, buy_score)
        elif sell_score > buy_score:
            signal = "SELL"
            confidence = min(100, sell_score)
        else:
            signal = "NEUTRAL"
            confidence = max(0, min(100, int(abs(ai_score))))
        
        if signal == "NEUTRAL" and abs(ai_score) >= 30:
            signal = f"AI-{ai_signal}"
            confidence = min(100, max(confidence, int(abs(ai_score))))
        
        signals[tf] = {
            "rsi": rsi,
            "price": current_price,
            "signal": signal,
            "confidence": confidence,
            "macd": macd_dir,
            "bb_position": "BELOW" if current_price < lower_bb else "ABOVE" if current_price > upper_bb else "MIDDLE",
            "stoch": stoch_k,
            "ai_signal": ai_signal,
            "ai_score": ai_score,
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
    table.add_column("Time", style="white", justify="center")
    table.add_column("TF", style="cyan", justify="center")
    table.add_column("RSI", style="magenta", justify="right")
    table.add_column("Price", style="white", justify="right")
    table.add_column("MACD", style="blue", justify="center")
    table.add_column("BB", style="green", justify="center")
    table.add_column("Stoch", style="yellow", justify="right")
    table.add_column("Signal", style="bold", justify="center")
    table.add_column("AI", style="cyan", justify="center")
    table.add_column("Conf%", style="red", justify="right")
    table.add_column("Stat", style="yellow", justify="center")
    table.add_column("Act", style="bold", justify="center")
    
    for tf, data in signals.items():
        tf_str = f"{tf}s" if tf < 60 else f"{tf//60}m"
        rsi = f"{data['rsi']:.1f}"
        price = f"{data['price']:.5f}"
        macd = data.get('macd', 'N/A')
        bb_pos = data.get('bb_position', 'N/A')
        stoch = f"{data.get('stoch', 50):.1f}"
        signal = data['signal']
        ai_signal = data.get('ai_signal', 'NEUTRAL')
        confidence = data.get('confidence', 0)
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = data.get('stable', 'UNSTABLE')
        
        # Signal color coding
        if "STRONG BUY" in signal or signal.startswith("AI-BUY"):
            signal_style = f"[bold green]{signal}[/bold green]"
            action = "[bold green]→ CALL ✓[/bold green]"
        elif "STRONG SELL" in signal or signal.startswith("AI-SELL"):
            signal_style = f"[bold red]{signal}[/bold red]"
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
        table.add_row(timestamp, tf_str, rsi, price, macd, bb_pos, stoch, signal_style, ai_signal, f"{confidence}%", status_style, action)
    
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
    timeframes = [60]  # Use 1-minute signals for higher stability

    signal_history = {}
    
    while True:
        try:
            console.clear()
            console.print(f"[bold cyan]🚀 Multi-Asset High-Accuracy Signals - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold cyan]\n")
            
            for symbol, asset_name in assets.items():
                signals = await generate_signals(symbol, timeframes)
                signals = smooth_signals(asset_name, signals, signal_history, min_stable=3)
                await display_signals(signals, asset_name)
                await display_asset_recommendation(asset_name, signals)
            
            console.print(f"\n[dim]Refreshing in 5 seconds... (Stable Monitoring)[/dim]")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏹️ Stopped by user.[/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]⚠️ Error: {e}[/red]")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())