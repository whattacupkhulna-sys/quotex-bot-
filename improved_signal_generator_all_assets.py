# Improved Quotex Real Signal Generator (Analyze ALL instruments + feature-style output)
# Use responsibly. Do not commit credentials to source control.

import os
import sys
import time
import asyncio
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Attempt to import Quotex client
try:
    from quotexapi.stable_api import Quotex
except Exception:
    Quotex = None

# -----------------------
# Configurable settings
# -----------------------
TIMEFRAME_SECONDS = 60            # candle timeframe to analyze
MARTINGALE_STEPS = 1              # textual only, not an automated martingale system
CONCURRENCY_LIMIT = 8             # how many instruments to analyze in parallel
MAX_SIGNALS_SHOWN = 150           # maximum signals to display per scan (cap output)
CANDLE_COUNT = 100                # candles per instrument
SCAN_INTERVAL_SECONDS = 30        # seconds between full scans
PIN_METHOD_NAMES = ("submit_pin", "verify_pin", "confirm_pin")  # adapt if needed

# -----------------------
# Timezone -> flag mapping (basic)
# Add/remove mappings as needed
# -----------------------
TZ_FLAG_MAP = {
    "+0600": "🇧🇩",  # Bangladesh
    "+0000": "🌍",
    "+0530": "🇮🇳",  # India
    "-0500": "🇺🇸",  # US Eastern (example)
    "+0100": "🇪🇺"
}

# ============================================================================
# TECHNICAL ANALYSIS (same improved implementations)
# ============================================================================

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
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)

    @staticmethod
    def calculate_ema(prices, period=20):
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

    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal_period=9):
        prices = list(prices)
        if len(prices) < slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"
        def ema_series(arr, period):
            arr = list(arr)
            if len(arr) < period:
                return []
            seed = float(np.mean(arr[:period]))
            out = [seed]
            mult = 2.0 / (period + 1.0)
            for price in arr[period:]:
                seed = (price - seed) * mult + seed
                out.append(seed)
            return out
        ema_fast = ema_series(prices, fast)
        ema_slow = ema_series(prices, slow)
        if not ema_slow:
            return 0.0, 0.0, 0.0, "NEUTRAL"
        offset_fast = len(ema_fast) - len(ema_slow)
        macd_series = []
        for i in range(len(ema_slow)):
            macd_series.append(ema_fast[offset_fast + i] - ema_slow[i])
        if len(macd_series) < signal_period:
            macd_line_last = macd_series[-1]
            return macd_line_last, 0.0, macd_line_last, "NEUTRAL"
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
    def __init__(self, client):
        self.client = client
        self.ta = TechnicalAnalysis()

    async def analyze_asset(self, asset, timeframe=TIMEFRAME_SECONDS, candle_count=CANDLE_COUNT):
        try:
            candles = await self.client.get_candles(
                par=asset,
                timeframe=timeframe,
                quantidade=candle_count,
                timestamp=int(time.time())
            )
            if not candles or isinstance(candles, str):
                return None
            try:
                candles_sorted = sorted(candles, key=lambda c: c.get("time", c.get("timestamp", 0)))
            except Exception:
                candles_sorted = candles
            close_prices = [float(c['close']) for c in candles_sorted if 'close' in c]
            if len(close_prices) < 20:
                return None
            rsi = self.ta.calculate_rsi(close_prices, period=14)
            macd_line, macd_signal_line, macd_hist, macd_signal = self.ta.calculate_macd(close_prices)
            upper_bb, middle_bb, lower_bb = self.ta.calculate_bollinger_bands(close_prices)
            ema_20 = self.ta.calculate_ema(close_prices, period=20)
            trend = self.ta.detect_trend(close_prices)
            current_price = close_prices[-1]
            signal_strength = 0
            direction = None
            reasons = []
            if rsi < 30:
                signal_strength += 25
                direction = "CALL"
                reasons.append(f"RSI Oversold ({rsi:.1f})")
            elif rsi > 70:
                signal_strength += 25
                direction = "PUT"
                reasons.append(f"RSI Overbought ({rsi:.1f})")
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
            if trend == "UPTREND" and direction == "CALL":
                signal_strength += 20
                reasons.append("Uptrend")
            elif trend == "DOWNTREND" and direction == "PUT":
                signal_strength += 20
                reasons.append("Downtrend")
            if signal_strength >= 50 and direction:
                return {
                    'asset': asset,
                    'direction': direction,
                    'strength': min(int(round(signal_strength)), 100),
                    'rsi': rsi,
                    'macd': macd_signal,
                    'trend': trend,
                    'price': current_price,
                    'reasons': reasons,
                    'timeframe': f"{timeframe}s",
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                }
            return None
        except Exception as e:
            console.print(f"[dim red]Error analyzing {asset}: {str(e)[:80]}[/dim red]")
            return None

# ============================================================================
# Helpers: credentials, async input, timezone format, instrument parsing
# ============================================================================

def load_credentials_from_env_or_dotenv(dotenv_path=".env"):
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

async def prompt_async(prompt_text=""):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, prompt_text)

def format_utc_offset_and_flag():
    local = datetime.now().astimezone()
    offset = local.utcoffset() or timedelta(0)
    # format like +6:00
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hh = abs(total_minutes) // 60
    mm = abs(total_minutes) % 60
    offset_str = f"{sign}{hh}:{mm:02d}"
    tzkey = f"{sign}{hh:02d}{mm:02d}"
    flag = TZ_FLAG_MAP.get(tzkey, "")
    return offset_str, flag, local.strftime("%H:%M")

def extract_instrument_id(item):
    """
    Try to extract an instrument identifier usable by get_candles/par.
    Accepts item returned by client.get_instruments() which varies by client implementation.
    """
    if item is None:
        return None
    # If item is a simple string
    if isinstance(item, str):
        return item
    # If dict-like
    if isinstance(item, dict):
        # common keys
        for key in ("name", "par", "id", "instrument", "title", "symbol"):
            if key in item and item[key]:
                return str(item[key])
        # maybe a nested structure
        if "data" in item and isinstance(item["data"], dict):
            for key in ("par", "name", "symbol"):
                if key in item["data"]:
                    return str(item["data"][key])
    # fallback to string representation
    try:
        return str(item)
    except Exception:
        return None

# ============================================================================
# Connection handling (with PIN attempts)
# ============================================================================

async def connect_with_retry(email, password, max_retries=3):
    if Quotex is None:
        console.print("[bold red]Quotex client not available (import failed). Install or provide module.[/bold red]")
        return None, False
    for attempt in range(1, max_retries + 1):
        try:
            console.print(f"\n[bold cyan]🔌 Connection attempt {attempt}/{max_retries}...[/bold cyan]")
            client = Quotex(email=email, password=password, lang="en", host=os.getenv("QUOTEX_HOST", "qxbroker.com"))
            check, reason = await client.connect()
            if check:
                console.print("[bold green]✅ Successfully connected to Quotex![/bold green]")
                return client, True
            reason_text = str(reason or "")
            console.print(f"[yellow]⚠️ Attempt {attempt} failed: {reason_text}[/yellow]")
            if "pin" in reason_text.lower() or "code" in reason_text.lower():
                console.print("[yellow]📧 Check email for PIN. You may have limited time to enter it.[/yellow]")
                pin = await prompt_async("Enter PIN code from email (or press Enter to skip): ")
                pin = pin.strip()
                if pin:
                    for m in PIN_METHOD_NAMES:
                        if hasattr(client, m):
                            try:
                                method = getattr(client, m)
                                # call method; handle coroutine or sync
                                if asyncio.iscoroutinefunction(method):
                                    await method(pin)
                                else:
                                    method(pin)
                                console.print(f"[dim]Called {m} on client with provided PIN.[/dim]")
                                break
                            except Exception as e:
                                console.print(f"[red]PIN submission via {m} failed: {e}[/red]")
                # retry connect after PIN attempt
                check2, reason2 = await client.connect()
                if check2:
                    console.print("[bold green]✅ Connected after PIN submission![/bold green]")
                    return client, True
                else:
                    console.print(f"[yellow]Still not connected: {reason2}[/yellow]")
            if attempt < max_retries:
                await asyncio.sleep(5)
        except Exception as e:
            console.print(f"[red]❌ Error on attempt {attempt}: {e}[/red]")
            if attempt < max_retries:
                await asyncio.sleep(5)
    return None, False

# ============================================================================
# Output formatting for the feature-style display
# ============================================================================

def print_feature_header(offset_str, flag, current_time):
    header = f"❈  UTC/GMT :   ( {offset_str} ) {flag}\nCurrent Time: {current_time}\n◇──◇──◇──◇──◇──◇──◇──◇"
    # print it multiple times for the decorative effect like the sample
    for _ in range(2):
        console.print("\n" + header + "\n")

def print_martingale_block():
    console.print("\n❈  1STEP MARTINGALE")
    console.print("❈  1MINUTE TIMEFRAME")
    console.print("❈  1STEP MARTINGALE")
    console.print("❈  1MINUTE TIMEFRAME\n")
    console.print("◇──◇──◇──◇──◇──◇──◇──◇\n")

def print_rules_block():
    console.print("\n⛩ RULES -\n")
    console.print("✧ MUST BE USE SAFETY MARGIN")
    console.print("✧ BACK 2 BACK 2 LOSS SKIP MUST\n")
    console.print("━━━━━━━━━━━━━━━━━⍟\n")
    console.print("✧  PYTHON x MAHIR  ✧")
    console.print("\n═══❰  OWNER  @LUX_DOT MAHIR  💸 ❱══❍⊱\n")

# ============================================================================
# Main scanning loop (analyze all instruments)
# ============================================================================

async def scan_all_instruments(client):
    gen = RealSignalGenerator(client)

    # fetch instruments list robustly
    try:
        instruments_raw = await client.get_instruments()
    except Exception as e:
        console.print(f"[red]Could not fetch instruments: {e}[/red]")
        instruments_raw = []

    instrument_ids = []
    if instruments_raw:
        # if it's a dict mapping categories -> lists, flatten
        if isinstance(instruments_raw, dict):
            for v in instruments_raw.values():
                if isinstance(v, list):
                    for item in v:
                        iid = extract_instrument_id(item)
                        if iid:
                            instrument_ids.append(iid)
        elif isinstance(instruments_raw, list):
            for item in instruments_raw:
                iid = extract_instrument_id(item)
                if iid:
                    instrument_ids.append(iid)
        else:
            # fallback: try to stringify
            try:
                for item in instruments_raw:
                    iid = extract_instrument_id(item)
                    if iid:
                        instrument_ids.append(iid)
            except Exception:
                pass

    # If still empty, fallback to common list
    if not instrument_ids:
        instrument_ids = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "USDCAD_otc", "EURGBP_otc", "EURJPY_otc", "GBPJPY_otc"
        ]

    console.print(f"[bold green]✅ Found {len(instrument_ids)} instruments (using {len(instrument_ids)} for scanning).[/bold green]")

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def analyze_with_semaphore(asset):
        async with sem:
            # small jitter to avoid synchronized bursts
            await asyncio.sleep(0.01)
            return await gen.analyze_asset(asset, timeframe=TIMEFRAME_SECONDS, candle_count=CANDLE_COUNT)

    # schedule tasks in batches to avoid flooding
    tasks = []
    for aid in instrument_ids:
        tasks.append(asyncio.create_task(analyze_with_semaphore(aid)))

    results = []
    # gather with progress - streaming gather to avoid waiting for all if you'd like; here we await all
    for t in asyncio.as_completed(tasks):
        try:
            res = await t
            if res:
                results.append(res)
            # small delay to be kind
            await asyncio.sleep(0.01)
        except Exception as e:
            console.print(f"[dim red]Analysis task error: {e}[/dim red]")

    # sort by strength desc then timestamp
    results.sort(key=lambda x: x['strength'], reverse=True)
    return results[:MAX_SIGNALS_SHOWN]

# ============================================================================
# Main entry
# ============================================================================

async def main():
    console.clear()
    console.print("\n[bold green]🚀 Starting Quotex Real Signal Generator (ALL INSTRUMENTS)...[/bold green]\n")

    email, password = load_credentials_from_env_or_dotenv()
    if not email or not password:
        console.print("[bold red]❌ No credentials found. Set QUOTEX_EMAIL and QUOTEX_PASSWORD env vars or a .env file.[/bold red]")
        return

    console.print(f"[green]✅ Email: {email}[/green]")
    console.print("[green]✅ Password: (hidden)[/green]\n")

    console.print("[bold yellow]⚠️ IMPORTANT: 2FA PIN CODE may be required[/bold yellow]")
    console.print("\n[dim]Press Enter when ready...[/dim]")
    await prompt_async()

    client, success = await connect_with_retry(email, password, max_retries=3)
    if not success or client is None:
        console.print("[bold red]❌ Connection failed.[/bold red]")
        return

    # attempt switch to demo safely
    try:
        if hasattr(client, "change_balance"):
            client.change_balance("PRACTICE")
    except Exception:
        pass

    try:
        # display looping scans
        while True:
            offset_str, flag, current_time = format_utc_offset_and_flag()
            print_feature_header(offset_str, flag, current_time)
            # Martingale / timeframe block
            print_martingale_block()

            # scan all instruments
            console.print("[bold cyan]🔍 Scanning instruments and generating signals...[/bold cyan]")
            signals = await scan_all_instruments(client)

            # Print signals in the requested compact form:
            # ⚙️EURUSD-OTC-18:26 - CALL
            if signals:
                for s in signals:
                    # Normalize asset name for display
                    asset_disp = s['asset'].upper().replace("_", "-")
                    # timestamp - use signal timestamp or current_time
                    ts = s.get('timestamp', datetime.now().strftime("%H:%M"))
                    # ensure minute format like HH:MM
                    if ":" not in ts:
                        ts = datetime.now().strftime("%H:%M")
                    console.print(f"⚙️{asset_disp}-{ts} - {s['direction']}")
            else:
                console.print("[yellow]⚠️ No strong signals found in this scan[/yellow]")

            # Print rules/footer
            print_rules_block()

            console.print(f"\n[dim]Next scan in {SCAN_INTERVAL_SECONDS} seconds... (Press Ctrl+C to stop)[/dim]\n")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)

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
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")