# Improved Quotex Real Signal Generator (async-safe, better indicators, safer env handling)
# Use responsibly. Do not commit real credentials to source control.

import os
import sys
import time
import asyncio
import numpy as np
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Try to import the Quotex client as before. Adjust your PYTHONPATH or install package.
try:
    from quotexapi.stable_api import Quotex
except Exception:
    # Keep running; we'll produce clearer error if client missing at runtime.
    Quotex = None

# ============================================================================
# TECHNICAL ANALYSIS INDICATORS (improved)
# ============================================================================

class TechnicalAnalysis:
    """Real technical analysis indicators (more standard implementations)."""

    @staticmethod
    def calculate_rsi(prices, period=14):
        """Calculate RSI using Wilder's smoothing.

        prices: iterable of floats (oldest -> newest)
        Returns last RSI value (float).
        """
        prices = np.asarray(prices, dtype=float)
        if prices.size < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # First average (simple) for the initial period
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # Wilder smoothing for subsequent values
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)

    @staticmethod
    def calculate_ema(prices, period=20):
        """Calculate EMA and return the last EMA value.

        Uses the SMA of the first 'period' as the seed.
        """
        prices = list(prices)
        n = len(prices)
        if n == 0:
            raise ValueError("Empty price list for EMA")
        if n < period:
            # fallback to simple average
            return float(np.mean(prices))

        sma = float(np.mean(prices[:period]))
        multiplier = 2.0 / (period + 1.0)
        ema = sma
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return float(ema)

    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal_period=9):
        """Calculate MACD final values: macd_line_last, signal_line_last, histogram_last, signal_str"""
        prices = list(prices)
        if len(prices) < slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"

        # build EMA series for fast and slow (compute recursively)
        def ema_series(arr, period):
            arr = list(arr)
            if len(arr) < period:
                return []
            # seed with SMA
            seed = float(np.mean(arr[:period]))
            out = [seed]
            multiplier = 2.0 / (period + 1.0)
            for price in arr[period:]:
                seed = (price - seed) * multiplier + seed
                out.append(seed)
            # align so that out[-1] corresponds to arr[-1]
            return out

        ema_fast = ema_series(prices, fast)
        ema_slow = ema_series(prices, slow)
        # We need to align both series to the same timestamps; ema_fast starts earlier (fast < slow) so align from where ema_slow starts
        if not ema_slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"

        # compute MACD series aligned to ema_slow
        # Determine offset: ema_fast length may be longer; align ends
        offset_fast = len(ema_fast) - len(ema_slow)
        macd_series = []
        for i in range(len(ema_slow)):
            macd_series.append(ema_fast[offset_fast + i] - ema_slow[i])

        # Signal line is EMA of macd_series
        if len(macd_series) < signal_period:
            # Not enough MACD history for signal line
            macd_line_last = macd_series[-1]
            return macd_line_last, 0.0, macd_line_last, "NEUTRAL"

        # calculate signal line (EMA of macd_series)
        signal_line = TechnicalAnalysis.calculate_ema(macd_series, period=signal_period)
        macd_line_last = macd_series[-1]
        histogram = macd_line_last - signal_line

        if histogram > 0:
            signal = "BULLISH"
        elif histogram < 0:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return float(macd_line_last), float(signal_line), float(histogram), signal

    @staticmethod
    def calculate_bollinger_bands(prices, period=20, std_dev=2):
        """Return (upper, middle, lower) for the last value; None if not enough data."""
        prices = np.asarray(prices)
        if prices.size < period:
            return None, None, None
        window = prices[-period:]
        sma = float(np.mean(window))
        sd = float(np.std(window, ddof=0))
        upper = sma + std_dev * sd
        lower = sma - std_dev * sd
        return float(upper), float(sma), float(lower)

    @staticmethod
    def detect_trend(prices, lookback=10, slope_threshold=1e-4):
        """Simple linear-fit slope over last `lookback` prices. Returns UPTREND/DOWNTREND/SIDEWAYS."""
        prices = list(prices)
        if len(prices) < lookback:
            return "SIDEWAYS"
        y = np.array(prices[-lookback:], dtype=float)
        x = np.arange(len(y))
        slope = np.polyfit(x, y, 1)[0]
        if slope > slope_threshold:
            return "UPTREND"
        if slope < -slope_threshold:
            return "DOWNTREND"
        return "SIDEWAYS"


# ============================================================================
# SIGNAL GENERATOR
# ============================================================================

class RealSignalGenerator:
    """Generate trading signals based on market data and indicators."""

    def __init__(self, client):
        self.client = client
        self.ta = TechnicalAnalysis()

    async def analyze_asset(self, asset, timeframe=60, candle_count=100):
        """Analyze a single asset and generate a signal dictionary or None."""
        try:
            # get_candles API: pass through and keep safe guards
            candles = await self.client.get_candles(
                par=asset,
                timeframe=timeframe,
                quantidade=candle_count,
                timestamp=int(time.time())
            )
            if not candles or isinstance(candles, str):
                return None

            # Ensure candles are sorted from oldest -> newest. Many APIs return newest first.
            try:
                # assume candles are dict-like with 'close' and 'time' or 'timestamp'
                candles_sorted = sorted(candles, key=lambda c: c.get("time", c.get("timestamp", 0)))
            except Exception:
                candles_sorted = candles

            close_prices = [float(c['close']) for c in candles_sorted if 'close' in c]
            if len(close_prices) < 20:
                return None

            # Indicators
            rsi = self.ta.calculate_rsi(close_prices, period=14)
            macd_line, macd_signal_line, macd_hist, macd_signal = self.ta.calculate_macd(close_prices)
            upper_bb, middle_bb, lower_bb = self.ta.calculate_bollinger_bands(close_prices)
            ema_20 = self.ta.calculate_ema(close_prices, period=20)
            trend = self.ta.detect_trend(close_prices)
            current_price = close_prices[-1]

            # Generate signal
            signal_strength = 0
            direction = None
            reasons = []

            # RSI
            if rsi < 30:
                signal_strength += 25
                direction = "CALL"
                reasons.append(f"RSI Oversold ({rsi:.1f})")
            elif rsi > 70:
                signal_strength += 25
                direction = "PUT"
                reasons.append(f"RSI Overbought ({rsi:.1f})")

            # MACD
            if macd_signal == "BULLISH":
                if direction in (None, "CALL"):
                    signal_strength += 20
                    direction = "CALL"
                    reasons.append("MACD Bullish")
            elif macd_signal == "BEARISH":
                if direction in (None, "PUT"):
                    signal_strength += 20
                    direction = "PUT"
                    reasons.append("MACD Bearish")

            # Bollinger
            if upper_bb is not None and lower_bb is not None:
                if current_price <= lower_bb:
                    if direction in (None, "CALL"):
                        signal_strength += 20
                        direction = "CALL"
                        reasons.append("Price at/near Lower BB")
                elif current_price >= upper_bb:
                    if direction in (None, "PUT"):
                        signal_strength += 20
                        direction = "PUT"
                        reasons.append("Price at/near Upper BB")

            # EMA20
            if current_price > ema_20:
                if direction in (None, "CALL"):
                    signal_strength += 15
                    direction = "CALL"
                    reasons.append("Above EMA20")
            elif current_price < ema_20:
                if direction in (None, "PUT"):
                    signal_strength += 15
                    direction = "PUT"
                    reasons.append("Below EMA20")

            # Trend confirmation
            if trend == "UPTREND" and direction == "CALL":
                signal_strength += 20
                reasons.append("Uptrend")
            elif trend == "DOWNTREND" and direction == "PUT":
                signal_strength += 20
                reasons.append("Downtrend")

            if signal_strength >= 50 and direction:
                return {
                    "asset": asset,
                    "direction": direction,
                    "strength": min(int(round(signal_strength)), 100),
                    "rsi": rsi,
                    "macd": macd_signal,
                    "trend": trend,
                    "price": current_price,
                    "reasons": reasons,
                    "timeframe": f"{timeframe}s",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            return None

        except Exception as e:
            console.print(f"[red]Error analyzing {asset}: {e}[/red]")
            return None


# ============================================================================
# ENV / CREDENTIALS
# ============================================================================

def load_credentials_from_env_or_dotenv(dotenv_path=".env"):
    """Prefer environment variables, fall back to .env parsing."""
    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")
    if email and password:
        return email, password

    p = Path(dotenv_path)
    if not p.exists():
        return None, None

    email = None
    password = None
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("QUOTEX_EMAIL="):
                email = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("QUOTEX_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"').strip("'")
    return email, password


# ============================================================================
# UI helpers
# ============================================================================

def print_header():
    console.clear()
    header = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║         🚀 QUOTEX REAL SIGNAL GENERATOR 🚀                   ║
    ║                                                               ║
    ║         Real-Time Technical Indicators                        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(header, style="bold cyan")


def create_signal_table(signals):
    table = Table(
        title="🎯 LIVE TRADING SIGNALS",
        box=box.DOUBLE_EDGE,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan"
    )
    table.add_column("Asset", style="cyan", width=12)
    table.add_column("Direction", style="bold", width=10)
    table.add_column("Strength", style="yellow", width=10)
    table.add_column("RSI", style="blue", width=8)
    table.add_column("MACD", style="green", width=10)
    table.add_column("Trend", style="magenta", width=10)
    table.add_column("Price", style="white", width=12)
    table.add_column("Time", style="dim", width=10)

    for s in signals:
        dir_style = "bold green" if s["direction"] == "CALL" else "bold red"
        strength_emoji = "🔥" if s["strength"] >= 80 else "⚡" if s["strength"] >= 60 else "💫"
        table.add_row(
            s["asset"],
            f"[{dir_style}]{s['direction']}[/{dir_style}]",
            f"{strength_emoji} {s['strength']}%",
            f"{s['rsi']:.1f}",
            s["macd"],
            s["trend"],
            f"{s['price']:.5f}",
            s["timestamp"]
        )
    return table


# ============================================================================
# CONNECTION + 2FA HANDLING
# ============================================================================

async def prompt_async(prompt_text=""):
    """Run blocking input in a thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, prompt_text)


async def connect_with_retry(email, password, max_retries=3):
    """Connect to Quotex with retry logic and optional interactive PIN entry.

    This function is generic: if the client exposes methods like `submit_pin` / `verify_pin`
    we attempt to call them. You must adapt names to the real client API.
    """
    if Quotex is None:
        console.print("[bold red]Quotex client library not available. Install or fix import.[/bold red]")
        return None, False

    for attempt in range(1, max_retries + 1):
        try:
            console.print(f"\n[bold cyan]🔌 Connection attempt {attempt}/{max_retries}...[/bold cyan]")
            client = Quotex(email=email, password=password, lang="en", host=os.getenv("QUOTEX_HOST", "qxbroker.com"))
            check, reason = await client.connect()

            if check:
                console.print("[bold green]✅ Connected successfully![/bold green]")
                return client, True

            # Not connected: reason may mention PIN
            reason_text = str(reason or "")
            console.print(f"[yellow]⚠️ Attempt {attempt} failed: {reason_text}[/yellow]")

            if "pin" in reason_text.lower() or "code" in reason_text.lower():
                console.print("[yellow]💡 Tip: Check your email for the PIN code and enter it when prompted.[/yellow]")
                # Prompt for PIN non-blockingly
                pin = await prompt_async("Enter PIN code from email (or press Enter to skip): ")
                pin = pin.strip()
                if pin:
                    # Try common method names; adapt if your client uses different API:
                    try:
                        if hasattr(client, "submit_pin"):
                            await client.submit_pin(pin)
                        elif hasattr(client, "verify_pin"):
                            await client.verify_pin(pin)
                        elif hasattr(client, "confirm_pin"):
                            await client.confirm_pin(pin)
                        else:
                            console.print("[dim]No known PIN submission method on client; skipping automatic submit.[/dim]")
                    except Exception as e:
                        console.print(f"[red]PIN submission failed: {e}[/red]")

                    # try to re-check connection quickly
                    check2, reason2 = await client.connect()
                    if check2:
                        console.print("[bold green]✅ Connected after PIN submission![/bold green]")
                        return client, True
                    else:
                        console.print(f"[yellow]Still not connected: {reason2}[/yellow]")

            if attempt < max_retries:
                console.print("[dim]Waiting 5 seconds before retry...[/dim]")
                await asyncio.sleep(5)

        except Exception as e:
            console.print(f"[red]❌ Error on attempt {attempt}: {e}[/red]")
            if attempt < max_retries:
                await asyncio.sleep(5)

    return None, False


# ============================================================================
# MAIN
# ============================================================================

async def main():
    print_header()
    console.print("\n[bold cyan]📧 Loading credentials...[/bold cyan]")
    email, password = load_credentials_from_env_or_dotenv()

    if not email or not password:
        console.print("[bold red]❌ No credentials found. Set QUOTEX_EMAIL and QUOTEX_PASSWORD env vars or create a .env file.[/bold red]")
        return

    console.print(f"[green]✅ Email: {email}[/green]")
    console.print(f"[green]✅ Password: {'*' * len(password)} (hidden)[/green]")

    console.print("\n[bold yellow]⚠️ IMPORTANT: 2FA PIN CODE may be required[/bold yellow]")
    console.print("[yellow]📧 Quotex may send a PIN code to your email[/yellow]")
    console.print("[yellow]⏱️ You may have limited time to enter it when prompted[/yellow]")
    console.print("\n[dim]Press Enter when ready...[/dim]")
    # non-blocking prompt
    await prompt_async()

    client, success = await connect_with_retry(email, password, max_retries=3)

    if not success or client is None:
        console.print("\n[bold red]❌ Connection failed. Switching to HYBRID MODE...[/bold red]")
        await asyncio.sleep(1)
        # try fallback import
        try:
            from quotex_pro_signals import main as pro_main  # may raise ImportError
            console.clear()
            await pro_main()
            return
        except Exception:
            console.print("[red]❌ Could not load Pro Signal Generator (or it failed).[/red]")
            return

    try:
        await asyncio.sleep(1)
        console.print("\n[bold cyan]🎮 Switching to DEMO account...[/bold cyan]")
        # Some clients' methods are synchronous; guard with hasattr and try/except.
        try:
            if hasattr(client, "change_balance"):
                client.change_balance("PRACTICE")
            else:
                console.print("[dim]No change_balance method on client; skipping.[/dim]")
        except Exception as e:
            console.print(f"[yellow]Could not switch balance: {e}[/yellow]")

        # Try to fetch balance
        try:
            if hasattr(client, "get_balance"):
                balance = await client.get_balance()
                console.print(f"[bold green]💰 Balance: ${balance}[/bold green]")
            else:
                console.print("[dim]Client has no get_balance method.[/dim]")
        except Exception:
            console.print("[yellow]⚠️ Could not fetch balance (continuing)...[/yellow]")

        console.print("\n[bold cyan]📊 Loading available assets...[/bold cyan]")
        instruments = []
        try:
            instruments = await client.get_instruments()
        except Exception:
            console.print("[yellow]⚠️ Could not fetch instruments; proceeding with default list.[/yellow]")

        if not instruments:
            console.print("[dim]Using default top assets list.[/dim]")
            instruments = [
                "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
                "USDCAD_otc", "EURGBP_otc", "EURJPY_otc", "GBPJPY_otc"
            ]

        console.print(f"[bold green]✅ Monitoring {len(instruments)} instruments (using selected top list)...[/bold green]")

        top_assets = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "USDCAD_otc", "EURGBP_otc", "EURJPY_otc", "GBPJPY_otc"
        ]

        generator = RealSignalGenerator(client)
        console.print("\n[bold cyan]🔍 Starting real-time market analysis...[/bold cyan]")

        iteration = 0
        while True:
            iteration += 1
            now_ts = datetime.now().strftime("%H:%M:%S")
            console.print(f"\n[bold yellow]═══ Scan #{iteration} - {now_ts} ═══[/bold yellow]\n")

            signals = []
            for asset in top_assets:
                # Non-verbose per-asset logging to keep output tidy
                signal = await generator.analyze_asset(asset, timeframe=60, candle_count=100)
                if signal:
                    signals.append(signal)
                await asyncio.sleep(0.4)

            if signals:
                signals.sort(key=lambda x: x["strength"], reverse=True)
                table = create_signal_table(signals)
                console.print(table)

                top = signals[0]
                reasons_text = "\n".join([f"  • {r}" for r in top["reasons"]])
                panel = Panel(
                    f"[bold]Asset:[/bold] {top['asset']}\n"
                    f"[bold]Direction:[/bold] {top['direction']}\n"
                    f"[bold]Strength:[/bold] {top['strength']}%\n"
                    f"[bold]Analysis:[/bold]\n{reasons_text}",
                    title="🏆 TOP SIGNAL",
                    border_style="bold green" if top["direction"] == "CALL" else "bold red",
                    expand=False
                )
                console.print("\n", panel)
            else:
                console.print("[yellow]⚠️ No strong signals found in this scan[/yellow]")

            console.print(f"\n[dim]Next scan in 30 seconds... (Press Ctrl+C to stop)[/dim]")
            await asyncio.sleep(30)

    except asyncio.CancelledError:
        console.print("\n[bold yellow]⚠️ System stopped[/bold yellow]")
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️ System stopped by user[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
    finally:
        console.print("\n[bold cyan]🔌 Closing connection...[/bold cyan]")
        try:
            if client:
                await client.close()
                console.print("[bold green]✅ Connection closed[/bold green]")
        except Exception:
            pass


if __name__ == "__main__":
    console.print("\n[bold green]🚀 Starting Quotex Real Signal Generator (improved)...[/bold green]\n")
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
    console.print("\n[bold cyan]✨ System shutdown complete[/bold cyan]\n")