#!/usr/bin/env python3
"""
Utility functions for Greedisgood Telegram Bot
"""

import asyncio
import sys
from datetime import datetime
from web3 import Web3
from eth_account import Account

def generate_test_wallet():
    """Generate a test wallet for development"""
    account = Account.create()
    print(f"Test Wallet Generated:")
    print(f"Address: {account.address}")
    print(f"Private Key: {account.key.hex()}")
    print("\n⚠️  NEVER use this wallet for real funds!")
    return account.address, account.key.hex()

def validate_bsc_address(address: str) -> bool:
    """Validate BSC address format"""
    try:
        Web3.to_checksum_address(address)
        return True
    except:
        return False

def format_usdt_amount(amount: float) -> str:
    """Format USDT amount for display"""
    return f"{amount:.2f} USDT"

def get_current_time() -> str:
    """Get current time formatted"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

async def test_database_connection():
    """Test database connection"""
    try:
        from database import db
        await db.init_db()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_web3_connection(rpc_url: str) -> bool:
    """Test Web3 connection to BSC"""
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if w3.is_connected():
            latest_block = w3.eth.block_number
            print(f"✅ BSC connection successful (Block: {latest_block})")
            return True
        else:
            print("❌ BSC connection failed")
            return False
    except Exception as e:
        print(f"❌ BSC connection error: {e}")
        return False

async def test_bot_token(token: str) -> bool:
    """Test Telegram bot token"""
    try:
        from aiogram import Bot
        bot = Bot(token=token)
        me = await bot.get_me()
        print(f"✅ Bot token valid: @{me.username}")
        await bot.session.close()
        return True
    except Exception as e:
        print(f"❌ Bot token invalid: {e}")
        return False

async def run_diagnostics():
    """Run full system diagnostics"""
    print("🔍 Running Greedisgood Bot Diagnostics")
    print("=" * 50)
    
    # Load configuration
    try:
        from config import Config
        Config.validate_config()
        print("✅ Configuration loaded")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    # Test database
    db_ok = await test_database_connection()
    
    # Test Web3 connection
    web3_ok = test_web3_connection(Config.BSC_RPC_URL)
    
    # Test bot token
    bot_ok = await test_bot_token(Config.BOT_TOKEN)
    
    # Test wallet
    wallet_ok = validate_bsc_address(Config.MASTER_WALLET_ADDRESS)
    if wallet_ok:
        print(f"✅ Master wallet address valid: {Config.MASTER_WALLET_ADDRESS}")
    else:
        print(f"❌ Master wallet address invalid: {Config.MASTER_WALLET_ADDRESS}")
    
    print("\n" + "=" * 50)
    if all([db_ok, web3_ok, bot_ok, wallet_ok]):
        print("✅ All systems operational!")
        return True
    else:
        print("❌ Some systems have issues. Please check configuration.")
        return False

def main():
    """Main utility function"""
    if len(sys.argv) < 2:
        print("Usage: python utils.py <command>")
        print("Commands:")
        print("  generate-wallet  - Generate test wallet")
        print("  diagnostics      - Run system diagnostics")
        print("  validate-address <address> - Validate BSC address")
        return
    
    command = sys.argv[1]
    
    if command == "generate-wallet":
        generate_test_wallet()
    
    elif command == "diagnostics":
        asyncio.run(run_diagnostics())
    
    elif command == "validate-address":
        if len(sys.argv) < 3:
            print("Please provide an address to validate")
            return
        
        address = sys.argv[2]
        if validate_bsc_address(address):
            print(f"✅ Valid BSC address: {address}")
        else:
            print(f"❌ Invalid BSC address: {address}")
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()