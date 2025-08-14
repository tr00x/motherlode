#!/usr/bin/env python3
"""
Quick start script for Greedisgood Telegram Bot
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")

def check_env_file():
    """Check if .env file exists and is configured"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found")
        print("Please copy .env.example to .env and configure it")
        sys.exit(1)
    
    # Check if basic configuration is set
    with open(env_path, 'r') as f:
        content = f.read()
        
    required_vars = [
        'BOT_TOKEN=your_bot_token_here',
        'ADMIN_ID=your_telegram_id_here',
        'MASTER_WALLET_PRIVATE_KEY=your_master_wallet_private_key_here'
    ]
    
    missing_config = []
    for var in required_vars:
        if var in content:
            missing_config.append(var.split('=')[0])
    
    if missing_config:
        print("❌ Please configure the following variables in .env:")
        for var in missing_config:
            print(f"   - {var}")
        sys.exit(1)
    
    print("✅ .env file configured")

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)

def main():
    """Main function"""
    print("🤖 Greedisgood Telegram Bot Launcher")
    print("=" * 40)
    
    # Check Python version
    check_python_version()
    
    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found")
        sys.exit(1)
    
    # Install dependencies
    install_dependencies()
    
    # Check .env configuration
    check_env_file()
    
    print("\n🚀 Starting bot...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Import and run the bot
        from main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please check if all dependencies are installed")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()