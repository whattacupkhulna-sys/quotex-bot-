# Quotex Real Signal Generator (Improved)

This repository contains an improved, async-safe signal generator for the Quotex API with enhanced technical indicators and optional 2FA (PIN) handling hooks.

Overview
- Improved implementations for RSI, EMA, MACD, Bollinger Bands, and simple trend detection.
- Async-friendly: avoids blocking calls inside asyncio event loop.
- Non-blocking PIN prompt support (requires adapting to your Quotex client API if it exposes PIN submission methods).
- Demo/hybrid fallback behavior preserved.

Files
- improved_signal_generator.py — main improved script with async-safe prompts and indicator implementations.
- requirements.txt — dependency list (see below).
- .env (optional) — store QUOTEX_EMAIL and QUOTEX_PASSWORD if you prefer not to use environment variables.

Requirements
- Python 3.10+ recommended
- Install dependencies:
  pip install -r requirements.txt

Note: quotexapi may not be available on PyPI. If you use a local copy (like a folder or cloned repo), either install it as a package or add its path to PYTHONPATH before running the script.

Quick setup
1. Install dependencies:
   pip install -r requirements.txt

2. Provide credentials (choose ONE):
   - Environment variables:
     export QUOTEX_EMAIL="you@example.com"
     export QUOTEX_PASSWORD="yourpassword"
   - OR create a `.env` file in the project root:
     QUOTEX_EMAIL="you@example.com"
     QUOTEX_PASSWORD="yourpassword"

3. (Optional) If the quotex client is a local module, install it:
   - python -m pip install -e path/to/local/quotexapi
   OR
   - export PYTHONPATH="/path/to/quotexapi:$PYTHONPATH"

Running
- Run the improved script:
  python improved_signal_generator.py

What the script does
- Connects to Quotex (with retry).
- Provides an interactive, non-blocking prompt to enter the 2FA/PIN if required.
- Switches to DEMO (PRACTICE) balance if available.
- Monitors a set of top FX assets and outputs signals in a rich table and panel.
- Continues scanning every 30 seconds until interrupted (Ctrl+C).

2FA / PIN Handling
- The script includes generic hooks that will attempt to call common methods on the client if they exist:
  - submit_pin(pin)
  - verify_pin(pin)
  - confirm_pin(pin)
- These are guesses: your actual client library may use different method names/signatures.
- To fully automate PIN submission, I need the actual Quotex client class (or at least the method names and signatures) for:
  - connect()
  - get_candles(...)
  - get_instruments()
  - change_balance()
  - get_balance()
  - close()
  - any PIN-related methods (names & how they should be called)

Please paste the Quotex client class (or the relevant method signatures) and I will adapt the code to call the exact PIN/API methods.

Troubleshooting
- If import fail for `quotexapi.stable_api`:
  - Install or add the package path to PYTHONPATH, or adjust the import path in improved_signal_generator.py.
- If you see Cloudflare or connection blocking:
  - The script falls back to a "HYBRID MODE" stub; you can implement/import a fallback module named `quotex_pro_signals` or handle the offline fallback differently.
- Don't commit .env with credentials into source control.

Next steps (I will do if you confirm)
1. Adapt the 2FA handling in improved_signal_generator.py to your real Quotex client API (I need the client class or method signatures).
2. Optionally: split code into modules, add unit tests, add GitHub Actions CI, or create a packaged install.

What I need from you to adapt 2FA now
- Paste the Quotex client class (the file or the class definition) or at least list the exact method names and signatures for:
  - connect()
  - submit_pin / verify_pin / confirm_pin (if any)
  - get_candles(par, timeframe, quantidade, timestamp) or the actual call signature
  - get_instruments()
  - change_balance(balance_type)
  - get_balance()
  - close()
  - any other relevant helper methods

Once you paste that, I will:
- Update improved_signal_generator.py to call the exact PIN/API methods.
- Provide a small patch (or updated file) you can drop into your project.

Would you like me to (A) generate the PIN-adapted script now if you paste the client methods, or (B) produce a test harness / unit tests for the TA functions first?
