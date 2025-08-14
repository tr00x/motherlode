import os
import asyncio
from datetime import datetime
from typing import Optional
from config import Config

class TransactionLogger:
    def __init__(self, log_file: str = "transactions.log"):
        self.log_file = log_file
        self.ensure_log_file_exists()
    
    def ensure_log_file_exists(self):
        """Ensure log file exists"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# Greedisgood Transaction Log\n")
                f.write("# Format: TIMESTAMP | TYPE | USER_ID | AMOUNT | FROM_ADDRESS | TO_ADDRESS | TX_HASH | STATUS | DETAILS\n")
    
    async def log_investment_created(self, user_id: int, amount: float, proxy_address: str):
        """Log new investment creation"""
        await self._write_log(
            log_type="INVESTMENT_CREATED",
            user_id=user_id,
            amount=amount,
            to_address=proxy_address,
            details=f"Proxy wallet generated for {amount} USDT"
        )
    
    async def log_payment_received(self, user_id: int, amount: float, from_address: str, 
                                  to_address: str, tx_hash: str):
        """Log payment received"""
        await self._write_log(
            log_type="PAYMENT_RECEIVED",
            user_id=user_id,
            amount=amount,
            from_address=from_address,
            to_address=to_address,
            tx_hash=tx_hash,
            status="CONFIRMED",
            details=f"Payment confirmed for {amount} USDT"
        )
    
    async def log_payout_sent(self, user_id: int, amount: float, to_address: str, tx_hash: str):
        """Log payout sent"""
        await self._write_log(
            log_type="PAYOUT_SENT",
            user_id=user_id,
            amount=amount,
            to_address=to_address,
            tx_hash=tx_hash,
            status="SENT",
            details=f"Payout sent {amount} USDT"
        )
    
    async def log_bnb_funding(self, proxy_address: str, amount: float, tx_hash: str):
        """Log BNB funding for proxy wallet"""
        await self._write_log(
            log_type="BNB_FUNDING",
            amount=amount,
            to_address=proxy_address,
            tx_hash=tx_hash,
            status="SENT",
            details=f"BNB gas funding {amount} BNB"
        )
    
    async def log_referral_bonus(self, referrer_id: int, referred_id: int, bonus_amount: float):
        """Log referral bonus earned"""
        await self._write_log(
            log_type="REFERRAL_BONUS",
            user_id=referrer_id,
            amount=bonus_amount,
            details=f"Referral bonus +{bonus_amount}% from user {referred_id}"
        )
    
    async def log_admin_action(self, admin_id: int, action: str, details: str):
        """Log admin actions"""
        await self._write_log(
            log_type="ADMIN_ACTION",
            user_id=admin_id,
            details=f"{action}: {details}"
        )
    
    async def _write_log(self, log_type: str, user_id: Optional[int] = None, 
                        amount: Optional[float] = None, from_address: Optional[str] = None,
                        to_address: Optional[str] = None, tx_hash: Optional[str] = None,
                        status: Optional[str] = None, details: str = ""):
        """Write log entry to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"{timestamp} | {log_type} | {user_id or 'N/A'} | {amount or 'N/A'} | "
        log_entry += f"{from_address or 'N/A'} | {to_address or 'N/A'} | {tx_hash or 'N/A'} | "
        log_entry += f"{status or 'N/A'} | {details}\n"
        
        # Write to file asynchronously
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_to_file, log_entry)
    
    def _write_to_file(self, log_entry: str):
        """Synchronous file write"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    async def get_logs(self, start_date: str = None, end_date: str = None, 
                      log_type: str = None) -> str:
        """Get logs with optional filtering"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._read_logs, start_date, end_date, log_type)
    
    def _read_logs(self, start_date: str = None, end_date: str = None, 
                  log_type: str = None) -> str:
        """Read and filter logs"""
        if not os.path.exists(self.log_file):
            return "No logs found."
        
        filtered_logs = []
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                
                # Apply filters
                if start_date and start_date not in line:
                    continue
                if end_date and end_date not in line:
                    continue
                if log_type and log_type not in line:
                    continue
                
                filtered_logs.append(line.strip())
        
        if not filtered_logs:
            return "No logs found for the specified criteria."
        
        return "\n".join(filtered_logs)

# Global logger instance
transaction_logger = TransactionLogger()