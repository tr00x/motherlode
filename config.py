import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Admin Configuration
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
    ADMIN_ID_2 = int(os.getenv('ADMIN_ID_2', 1879631407))  # Теймураз
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        return user_id in [Config.ADMIN_ID, Config.ADMIN_ID_2]
    
    @staticmethod
    def get_admin_name(user_id: int) -> str:
        if user_id == Config.ADMIN_ID:
            return "Создатель"
        elif user_id == Config.ADMIN_ID_2:
            return "Теймураз"
        return "Администратор"
    
    # Blockchain Configuration
    BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/')
    USDT_CONTRACT_ADDRESS = os.getenv('USDT_CONTRACT_ADDRESS', '0x55d398326f99059fF775485246999027B3197955')
    MASTER_WALLET_PRIVATE_KEY = os.getenv('MASTER_WALLET_PRIVATE_KEY')
    MASTER_WALLET_ADDRESS = os.getenv('MASTER_WALLET_ADDRESS')
    
    # Investment Configuration
    MIN_INVESTMENT = float(os.getenv('MIN_INVESTMENT', 10))
    MAX_INVESTMENT = float(os.getenv('MAX_INVESTMENT', 100))
    BASE_PERCENTAGE = float(os.getenv('BASE_PERCENTAGE', 1.0))
    WORKING_HOURS_START = int(os.getenv('WORKING_HOURS_START', 10))
    WORKING_HOURS_END = int(os.getenv('WORKING_HOURS_END', 22))
    INVESTMENT_TIMEOUT_MINUTES = int(os.getenv('INVESTMENT_TIMEOUT_MINUTES', 20))
    PAYOUT_DELAY_HOURS = int(os.getenv('PAYOUT_DELAY_HOURS', 24))
    
    # Referral Configuration
    REFERRAL_BONUS_PERCENTAGE = float(os.getenv('REFERRAL_BONUS_PERCENTAGE', 0.1))
    
    # Gas Configuration
    BNB_GAS_AMOUNT = float(os.getenv('BNB_GAS_AMOUNT', 0.0001))
    
    # Database
    DATABASE_PATH = 'greedisgood.db'
    
    # Translations
    @staticmethod
    def load_translations():
        with open('translations.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def validate_config():
        """Validate that all required configuration is present"""
        required_vars = [
            'BOT_TOKEN'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(Config, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # For testing without wallet
        if not Config.MASTER_WALLET_PRIVATE_KEY:
            Config.MASTER_WALLET_PRIVATE_KEY = "0x" + "0" * 64  # Test private key
        if not Config.MASTER_WALLET_ADDRESS:
            Config.MASTER_WALLET_ADDRESS = "0x" + "0" * 40  # Test address
        
        return True

# Global translations
TRANSLATIONS = Config.load_translations()