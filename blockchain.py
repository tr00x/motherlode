import asyncio
import secrets
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from typing import Optional, Dict, Any
import json
from config import Config
from database import db

# USDT ABI (simplified for transfer functions)
USDT_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

class BlockchainManager:
    def __init__(self):
        self.test_mode = Config.MASTER_WALLET_PRIVATE_KEY.startswith('0x000000')
        
        if not self.test_mode:
            self.w3 = Web3(Web3.HTTPProvider(Config.BSC_RPC_URL))
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # USDT contract
            self.usdt_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(Config.USDT_CONTRACT_ADDRESS),
                abi=USDT_ABI
            )
            
            # Master wallet
            self.master_account = Account.from_key(Config.MASTER_WALLET_PRIVATE_KEY)
        else:
            print("⚠️  Running in TEST MODE - blockchain functions disabled")
            self.w3 = None
            self.usdt_contract = None
            self.master_account = None
        
        # USDT decimals (usually 18 for BEP20 USDT)
        self.usdt_decimals = 18
    
    def generate_proxy_wallet(self) -> Dict[str, str]:
        """Generate new proxy wallet"""
        private_key = secrets.token_hex(32)
        account = Account.from_key(private_key)
        
        return {
            'address': account.address,
            'private_key': private_key
        }
    
    async def create_proxy_wallets(self, count: int = 10):
        """Pre-generate proxy wallets"""
        for _ in range(count):
            wallet = self.generate_proxy_wallet()
            await db.add_proxy_wallet(wallet['address'], wallet['private_key'])
    
    async def get_proxy_wallet(self) -> Optional[Dict[str, str]]:
        """Get available proxy wallet and fund it with BNB for gas"""
        wallet = await db.get_unused_proxy_wallet()
        if not wallet:
            # Generate new wallet if none available
            new_wallet = self.generate_proxy_wallet()
            await db.add_proxy_wallet(new_wallet['address'], new_wallet['private_key'])
            wallet = new_wallet
        
        # Fund wallet with BNB for gas
        await self.fund_proxy_wallet_with_gas(wallet['address'])
        return wallet
    
    async def fund_proxy_wallet_with_gas(self, proxy_address: str) -> bool:
        """Fund proxy wallet with BNB for gas fees"""
        try:
            # Check if master wallet has enough BNB
            master_balance = self.get_bnb_balance(Config.MASTER_WALLET_ADDRESS)
            gas_amount = Config.BNB_GAS_AMOUNT
            
            if master_balance < gas_amount:
                # Notify admin about insufficient balance
                await self.notify_admin_insufficient_bnb(master_balance, gas_amount)
                return False
            
            # Clear insufficient BNB flag if balance is restored
            bnb_insufficient = await db.get_setting('bnb_insufficient', 'false')
            if bnb_insufficient.lower() == 'true':
                await db.set_setting('bnb_insufficient', 'false')
                print(f"✅ BNB balance restored. Investment acceptance resumed.")
                
                # Notify admin about restoration
                if hasattr(self, 'bot') and self.bot:
                    message = f"✅ BNB баланс восстановлен!\n\n"
                    message += f"💰 Текущий баланс: {master_balance:.6f} BNB\n"
                    message += f"🟢 Приём новых инвестиций возобновлён."
                    await self.send_admin_notification(message)
            
            # Send BNB to proxy wallet
            tx_hash = await self.send_bnb(proxy_address, gas_amount)
            
            if tx_hash:
                print(f"Funded proxy wallet {proxy_address} with {gas_amount} BNB. TX: {tx_hash}")
                return True
            else:
                print(f"Failed to fund proxy wallet {proxy_address}")
                return False
        
        except Exception as e:
            print(f"Error funding proxy wallet {proxy_address}: {e}")
            return False
    
    async def notify_admin_insufficient_bnb(self, current_balance: float, required_amount: float):
        """Notify admin about insufficient BNB balance"""
        try:
            # Store notification in database for admin panel to show
            await db.set_setting('bnb_insufficient', 'true')
            await db.set_setting('bnb_current_balance', str(current_balance))
            await db.set_setting('bnb_required_amount', str(required_amount))
            
            print(f"⚠️ CRITICAL: Insufficient BNB balance {current_balance:.6f} < {required_amount:.6f}")
            print(f"Investment acceptance suspended until BNB balance is restored")
        except Exception as e:
            print(f"Failed to store BNB insufficient notification: {e}")
    
    def set_bot_instance(self, bot_instance):
        """Set bot instance for notifications"""
        self.bot = bot_instance
    
    async def send_admin_notification(self, message: str):
        """Send notification to admin if bot instance is available"""
        if hasattr(self, 'bot') and self.bot:
            try:
                await self.bot.send_message(Config.ADMIN_ID, message)
            except Exception as e:
                print(f"Failed to send admin notification: {e}")
    
    def get_usdt_balance(self, address: str) -> float:
        """Get USDT balance for address"""
        if self.test_mode:
            return 1000.0  # Test balance
        
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.usdt_contract.functions.balanceOf(checksum_address).call()
            balance = balance_wei / (10 ** self.usdt_decimals)
            return balance
        except Exception as e:
            print(f"Error getting balance for {address}: {e}")
            return 0.0
    
    def get_bnb_balance(self, address: str) -> float:
        """Get BNB balance for address"""
        if self.test_mode:
            return 1.0  # Test balance
        
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.w3.eth.get_balance(checksum_address)
            balance = self.w3.from_wei(balance_wei, 'ether')
            return float(balance)
        except Exception as e:
            print(f"Error getting BNB balance for {address}: {e}")
            return 0.0
    
    def get_latest_transactions(self, address: str, from_block: int = None) -> list:
        """Get latest transactions for address"""
        try:
            checksum_address = Web3.to_checksum_address(address)
            
            if from_block is None:
                from_block = self.w3.eth.block_number - 1000  # Last 1000 blocks
            
            # Get Transfer events to this address
            transfer_filter = self.usdt_contract.events.Transfer.create_filter(
                fromBlock=from_block,
                toBlock='latest',
                argument_filters={'to': checksum_address}
            )
            
            events = transfer_filter.get_all_entries()
            
            transactions = []
            for event in events:
                tx_hash = event['transactionHash'].hex()
                tx = self.w3.eth.get_transaction(tx_hash)
                
                transactions.append({
                    'hash': tx_hash,
                    'from': event['args']['from'],
                    'to': event['args']['to'],
                    'value': event['args']['value'] / (10 ** self.usdt_decimals),
                    'block_number': event['blockNumber'],
                    'timestamp': self.w3.eth.get_block(event['blockNumber'])['timestamp']
                })
            
            return sorted(transactions, key=lambda x: x['timestamp'], reverse=True)
        
        except Exception as e:
            print(f"Error getting transactions for {address}: {e}")
            return []
    
    async def send_bnb(self, to_address: str, amount: float, private_key: str = None) -> Optional[str]:
        """Send BNB to address"""
        if self.test_mode:
            print(f"TEST MODE: Would send {amount} BNB to {to_address}")
            return "0x" + "test_bnb_hash" + "0" * 40  # Test tx hash
        
        try:
            # Use master wallet if no private key provided
            if private_key is None:
                private_key = Config.MASTER_WALLET_PRIVATE_KEY
            
            account = Account.from_key(private_key)
            from_address = account.address
            
            # Check balance
            balance = self.get_bnb_balance(from_address)
            if balance < amount:
                print(f"Insufficient BNB balance: {balance} < {amount}")
                return None
            
            # Prepare transaction
            to_checksum = Web3.to_checksum_address(to_address)
            amount_wei = self.w3.to_wei(amount, 'ether')
            
            # Build transaction
            transaction = {
                'to': to_checksum,
                'value': amount_wei,
                'gas': 21000,  # Standard gas for BNB transfer
                'gasPrice': self.w3.to_wei('5', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(from_address)
            }
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                return tx_hash.hex()
            else:
                print(f"BNB transaction failed: {tx_hash.hex()}")
                return None
        
        except Exception as e:
            print(f"Error sending BNB: {e}")
            return None
    
    async def send_usdt(self, to_address: str, amount: float, private_key: str = None) -> Optional[str]:
        """Send USDT to address"""
        if self.test_mode:
            print(f"TEST MODE: Would send {amount} USDT to {to_address}")
            return "0x" + "test_transaction_hash" + "0" * 40  # Test tx hash
        
        try:
            # Use master wallet if no private key provided
            if private_key is None:
                private_key = Config.MASTER_WALLET_PRIVATE_KEY
            
            account = Account.from_key(private_key)
            from_address = account.address
            
            # Check balance
            balance = self.get_usdt_balance(from_address)
            if balance < amount:
                print(f"Insufficient balance: {balance} < {amount}")
                return None
            
            # Prepare transaction
            to_checksum = Web3.to_checksum_address(to_address)
            amount_wei = int(amount * (10 ** self.usdt_decimals))
            
            # Build transaction
            transaction = self.usdt_contract.functions.transfer(
                to_checksum, amount_wei
            ).build_transaction({
                'from': from_address,
                'gas': 100000,
                'gasPrice': self.w3.to_wei('5', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(from_address)
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                return tx_hash.hex()
            else:
                print(f"Transaction failed: {tx_hash.hex()}")
                return None
        
        except Exception as e:
            print(f"Error sending USDT: {e}")
            return None
    
    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid"""
        try:
            Web3.to_checksum_address(address)
            return True
        except:
            return False
    
    async def monitor_proxy_wallet(self, address: str, expected_amount: float, 
                                  timeout_minutes: int = 20) -> Optional[Dict[str, Any]]:
        """Monitor proxy wallet for incoming payment"""
        if self.test_mode:
            print(f"TEST MODE: Simulating payment of {expected_amount} USDT to {address}")
            await asyncio.sleep(5)  # Simulate short wait
            return {
                'tx_hash': '0x' + 'test_payment_hash' + '0' * 40,
                'from_address': '0x' + '1' * 40,
                'amount': expected_amount,
                'timestamp': int(asyncio.get_event_loop().time())
            }
        
        start_block = self.w3.eth.block_number
        timeout_seconds = timeout_minutes * 60
        check_interval = 30  # Check every 30 seconds
        
        for _ in range(timeout_seconds // check_interval):
            try:
                # Get recent transactions
                transactions = self.get_latest_transactions(address, start_block)
                
                for tx in transactions:
                    if abs(tx['value'] - expected_amount) < 0.01:  # Allow small difference
                        return {
                            'tx_hash': tx['hash'],
                            'from_address': tx['from'],
                            'amount': tx['value'],
                            'timestamp': tx['timestamp']
                        }
                
                await asyncio.sleep(check_interval)
            
            except Exception as e:
                print(f"Error monitoring wallet {address}: {e}")
                await asyncio.sleep(check_interval)
        
        return None  # Timeout
    
    async def process_payouts(self):
        """Process pending payouts"""
        try:
            # Check if payouts are enabled
            payouts_enabled = await db.get_setting('payouts_enabled', 'true')
            if payouts_enabled.lower() != 'true':
                print("Payouts are disabled")
                return
            
            pending_payouts = await db.get_pending_payouts()
            
            for payout in pending_payouts:
                try:
                    tx_hash = await self.send_usdt(
                        payout['payout_address'],
                        payout['payout_amount']
                    )
                    
                    if tx_hash:
                        await db.mark_investment_paid(payout['id'], tx_hash)
                        print(f"Payout sent: {payout['payout_amount']} USDT to {payout['payout_address']}")
                    else:
                        print(f"Failed to send payout for investment {payout['id']}")
                
                except Exception as e:
                    print(f"Error processing payout {payout['id']}: {e}")
        
        except Exception as e:
            print(f"Error in process_payouts: {e}")

# Global blockchain manager instance
blockchain = BlockchainManager()