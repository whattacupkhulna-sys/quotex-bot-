#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║        🚀 MAHIR X QUOTEX - PROFESSIONAL TRADING SYSTEM 🚀        ║
║                                                                  ║
║              Real-Time Signal Generator & Auto-Trader            ║
║                    Powered by Advanced AI Logic                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Author: MAHIR
Version: 3.0 - Production Ready
Status: REAL TRADING SYSTEM
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Rich console for beautiful output
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich import box
from rich.text import Text

console = Console()

# Color scheme
NEON_GREEN = "#00ff41"
NEON_BLUE = "#00d4ff"
NEON_PURPLE = "#b026ff"
NEON_YELLOW = "#ffea00"
NEON_RED = "#ff0055"

class MahirQuotexLauncher:
    """Professional launcher for Mahir's Quotex trading system"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_path = self.base_dir / "config.json"
        self.session_path = self.base_dir / "session.json"
        self.sessions_dir = self.base_dir / "sessions"
        self.email = None
        self.password = None
        self.ssid = None
        
    def print_banner(self):
        """Display the professional banner"""
        banner = f"""
[bold {NEON_PURPLE}]╔══════════════════════════════════════════════════════════════════╗[/]
[bold {NEON_PURPLE}]║[/]                                                                  [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]║[/]        [bold {NEON_GREEN}]🚀 MAHIR X QUOTEX - TRADING SYSTEM 🚀[/]                [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]║[/]                                                                  [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]║[/]              [bold {NEON_BLUE}]Real-Time Signal Generator & Auto-Trader[/]            [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]║[/]                    [bold {NEON_YELLOW}]Powered by Advanced AI Logic[/]                  [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]║[/]                                                                  [bold {NEON_PURPLE}]║[/]
[bold {NEON_PURPLE}]╚══════════════════════════════════════════════════════════════════╝[/]

[bold {NEON_BLUE}]System Status:[/] [bold {NEON_GREEN}]ONLINE[/]
[bold {NEON_BLUE}]Version:[/] [bold white]3.0 - Production Ready[/]
[bold {NEON_BLUE}]Mode:[/] [bold {NEON_YELLOW}]REAL TRADING[/]
[bold {NEON_BLUE}]Time:[/] [bold white]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]
"""
        console.print(banner)
        
    def load_credentials(self) -> bool:
        """Load credentials from config files"""
        try:
            # Try config.json first
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.email = config.get('email')
                    self.password = config.get('password')
                    console.print(f"[{NEON_GREEN}]✓[/] Loaded credentials from config.json")
                    return True
            
            # Try sessions/config.json
            sessions_config = self.sessions_dir / "config.json"
            if sessions_config.exists():
                with open(sessions_config, 'r') as f:
                    config = json.load(f)
                    self.email = config.get('email')
                    self.password = config.get('password')
                    console.print(f"[{NEON_GREEN}]✓[/] Loaded credentials from sessions/config.json")
                    return True
            
            # Try environment variables
            from dotenv import load_dotenv
            env_path = self.base_dir / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                self.email = os.getenv('QUOTEX_EMAIL')
                self.password = os.getenv('QUOTEX_PASSWORD')
                if self.email and self.password:
                    console.print(f"[{NEON_GREEN}]✓[/] Loaded credentials from .env")
                    return True
            
            console.print(f"[{NEON_RED}]✗[/] No credentials found!")
            return False
            
        except Exception as e:
            console.print(f"[{NEON_RED}]✗[/] Error loading credentials: {e}")
            return False
    
    def check_session(self) -> bool:
        """Check if valid session exists"""
        try:
            # Check session.json
            if self.session_path.exists():
                with open(self.session_path, 'r') as f:
                    session = json.load(f)
                    self.ssid = session.get('ssid')
                    if self.ssid:
                        console.print(f"[{NEON_GREEN}]✓[/] Found existing session (SSID)")
                        return True
            
            # Check sessions/session.json
            sessions_file = self.sessions_dir / "session.json"
            if sessions_file.exists():
                with open(sessions_file, 'r') as f:
                    session = json.load(f)
                    # Try demo or live
                    self.ssid = session.get('demo') or session.get('live')
                    if self.ssid:
                        console.print(f"[{NEON_GREEN}]✓[/] Found existing session in sessions/")
                        return True
            
            console.print(f"[{NEON_YELLOW}]⚠[/] No existing session found")
            return False
            
        except Exception as e:
            console.print(f"[{NEON_YELLOW}]⚠[/] Error checking session: {e}")
            return False
    
    async def run_login(self) -> bool:
        """Run the login script to get SSID"""
        try:
            console.print(f"\n[{NEON_BLUE}]→[/] Starting Playwright login process...")
            console.print(f"[{NEON_YELLOW}]⚠[/] A browser window will open - please wait...")
            
            # Import and run login
            from login import QuotexBot, Credentials
            
            creds = Credentials(email=self.email, password=self.password)
            bot = QuotexBot(creds, headless=False)
            
            await bot.run()
            
            # Check if SSID was saved
            if self.check_session():
                console.print(f"[{NEON_GREEN}]✓[/] Login successful! SSID obtained.")
                return True
            else:
                console.print(f"[{NEON_RED}]✗[/] Login failed - no SSID obtained")
                return False
                
        except Exception as e:
            console.print(f"[{NEON_RED}]✗[/] Login error: {e}")
            return False
    
    async def run_test(self) -> bool:
        """Run test1.py to verify connection"""
        try:
            console.print(f"\n[{NEON_BLUE}]→[/] Running connection test...")
            
            # Import test script
            import test1
            
            # Run the main function
            await test1.main()
            
            console.print(f"[{NEON_GREEN}]✓[/] Test completed successfully!")
            return True
            
        except Exception as e:
            console.print(f"[{NEON_RED}]✗[/] Test error: {e}")
            return False
    
    async def run_signal_generator(self):
        """Run the improved signal generator"""
        try:
            console.print(f"\n[{NEON_BLUE}]→[/] Starting Real-Time Signal Generator...")
            console.print(f"[{NEON_GREEN}]✓[/] Connecting to live market data...\n")
            
            # Import signal generator
            sys.path.insert(0, str(self.base_dir.parent))
            from improved_signal_generator import main as signal_main
            
            # Run signal generator
            await signal_main()
            
        except KeyboardInterrupt:
            console.print(f"\n[{NEON_YELLOW}]⚠[/] Signal generator stopped by user")
        except Exception as e:
            console.print(f"[{NEON_RED}]✗[/] Signal generator error: {e}")
    
    def show_menu(self) -> str:
        """Display interactive menu"""
        console.print(f"\n[bold {NEON_PURPLE}]═══════════════════════════════════════════════════════[/]")
        console.print(f"[bold {NEON_BLUE}]MAIN MENU[/]")
        console.print(f"[bold {NEON_PURPLE}]═══════════════════════════════════════════════════════[/]\n")
        
        table = Table(show_header=False, box=box.SIMPLE, border_style=NEON_BLUE)
        table.add_column("Option", style=f"bold {NEON_YELLOW}")
        table.add_column("Description", style="white")
        
        table.add_row("1", "🔐 Login to Quotex (Get SSID)")
        table.add_row("2", "🧪 Test Connection")
        table.add_row("3", "📊 Run Signal Generator (LIVE)")
        table.add_row("4", "🔄 Full Setup (Login → Test → Signals)")
        table.add_row("5", "❌ Exit")
        
        console.print(table)
        console.print(f"\n[bold {NEON_PURPLE}]═══════════════════════════════════════════════════════[/]")
        
        choice = console.input(f"[bold {NEON_GREEN}]Enter your choice (1-5):[/] ")
        return choice.strip()
    
    async def run(self):
        """Main launcher flow"""
        self.print_banner()
        
        # Load credentials
        if not self.load_credentials():
            console.print(f"\n[{NEON_RED}]✗ FATAL:[/] No credentials found!")
            console.print(f"[{NEON_YELLOW}]Please ensure config.json or .env exists with your credentials[/]")
            return
        
        console.print(f"[{NEON_GREEN}]✓[/] Email: {self.email}")
        
        # Check for existing session
        has_session = self.check_session()
        
        while True:
            choice = self.show_menu()
            
            if choice == "1":
                await self.run_login()
                
            elif choice == "2":
                if not has_session and not self.check_session():
                    console.print(f"[{NEON_RED}]✗[/] No session found! Please login first (Option 1)")
                else:
                    await self.run_test()
                    
            elif choice == "3":
                if not has_session and not self.check_session():
                    console.print(f"[{NEON_RED}]✗[/] No session found! Please login first (Option 1)")
                else:
                    await self.run_signal_generator()
                    
            elif choice == "4":
                # Full setup
                console.print(f"\n[{NEON_BLUE}]→[/] Starting full setup process...\n")
                
                # Step 1: Login
                if await self.run_login():
                    # Step 2: Test
                    await asyncio.sleep(2)
                    if await self.run_test():
                        # Step 3: Run signals
                        await asyncio.sleep(2)
                        await self.run_signal_generator()
                        
            elif choice == "5":
                console.print(f"\n[bold {NEON_PURPLE}]╔══════════════════════════════════════════════════════════════════╗[/]")
                console.print(f"[bold {NEON_PURPLE}]║[/]                                                                  [bold {NEON_PURPLE}]║[/]")
                console.print(f"[bold {NEON_PURPLE}]║[/]        [bold {NEON_GREEN}]✨ MAHIR QUOTEX SYSTEM SHUTDOWN COMPLETE ✨[/]           [bold {NEON_PURPLE}]║[/]")
                console.print(f"[bold {NEON_PURPLE}]║[/]                                                                  [bold {NEON_PURPLE}]║[/]")
                console.print(f"[bold {NEON_PURPLE}]╚══════════════════════════════════════════════════════════════════╝[/]\n")
                break
                
            else:
                console.print(f"[{NEON_RED}]✗[/] Invalid choice! Please select 1-5")

if __name__ == "__main__":
    try:
        launcher = MahirQuotexLauncher()
        asyncio.run(launcher.run())
    except KeyboardInterrupt:
        console.print(f"\n[{NEON_YELLOW}]⚠[/] System interrupted by user")
    except Exception as e:
        console.print(f"\n[{NEON_RED}]✗ FATAL ERROR:[/] {e}")
        import traceback
        traceback.print_exc()
