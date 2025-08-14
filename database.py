import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import Config

class Database:
    def __init__(self, db_path: str = Config.DATABASE_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT DEFAULT 'ru',
                    referrer_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_referrals INTEGER DEFAULT 0,
                    active_referrals INTEGER DEFAULT 0,
                    referral_bonus REAL DEFAULT 0.0
                )
            """)
            
            # Investments table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS investments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    proxy_address TEXT,
                    sender_address TEXT,
                    payout_address TEXT,
                    payout_amount REAL,
                    status TEXT DEFAULT 'pending',
                    plan_type TEXT DEFAULT 'daily',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    payout_date TIMESTAMP,
                    tx_hash TEXT,
                    payout_tx_hash TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Investment plans table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS investment_plans (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    percentage REAL,
                    duration_days INTEGER,
                    min_amount REAL,
                    max_amount REAL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default plans
            await db.execute("""
                INSERT OR IGNORE INTO investment_plans 
                (id, name, description, percentage, duration_days, min_amount, max_amount, is_active)
                VALUES 
                ('daily', 'Ежедневный', 'Выплаты каждый день', 1.0, 1, 10, 100, TRUE),
                ('weekly', 'Еженедельный', 'Выплаты каждую неделю (скоро)', 7.5, 7, 50, 500, FALSE)
            """)
            
            # Create indexes for better performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_investments_user_id ON investments(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_investments_created_at ON investments(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_referrer_id ON users(referrer_id)")
            
            # Proxy wallets table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS proxy_wallets (
                    address TEXT PRIMARY KEY,
                    private_key TEXT,
                    is_used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Settings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default settings
            await db.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES 
                ('payouts_enabled', 'true'),
                ('daily_percentage', '1.0'),
                ('admin_password', ?)
            """, (Config.ADMIN_PASSWORD,))
            
            await db.commit()
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                      last_name: str = None, language_code: str = 'ru', referrer_id: int = None):
        """Add new user to database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, language_code, referrer_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code, referrer_id))
            
            # Update referrer's total referrals count
            if referrer_id:
                await db.execute("""
                    UPDATE users SET total_referrals = total_referrals + 1
                    WHERE user_id = ?
                """, (referrer_id,))
            
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_user_language(self, user_id: int, language_code: str):
        """Update user's language preference"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET language_code = ? WHERE user_id = ?",
                (language_code, user_id)
            )
            await db.commit()
    
    async def create_investment(self, user_id: int, amount: float, proxy_address: str, plan_type: str = 'daily') -> int:
        """Create new investment record"""
        # Get plan details
        plan = await self.get_investment_plan(plan_type)
        if not plan:
            raise ValueError(f"Investment plan {plan_type} not found")
        
        payout_date = datetime.now() + timedelta(days=plan['duration_days'])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO investments 
                (user_id, amount, proxy_address, plan_type, payout_date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, amount, proxy_address, plan_type, payout_date))
            
            investment_id = cursor.lastrowid
            await db.commit()
            return investment_id
    
    async def get_investment_plans(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all investment plans"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM investment_plans"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY duration_days"
            
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_investment_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get specific investment plan"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM investment_plans WHERE id = ?", (plan_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_investment_plan(self, plan_id: str, **kwargs):
        """Update investment plan"""
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [plan_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE investment_plans SET {set_clause} WHERE id = ?",
                values
            )
            await db.commit()
    
    async def update_investment_payment(self, investment_id: int, sender_address: str, 
                                       tx_hash: str, payout_address: str = None):
        """Update investment with payment details"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get investment details
            async with db.execute(
                "SELECT user_id, amount FROM investments WHERE id = ?", (investment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                
                user_id, amount = row
            
            # Get investment plan and user's referral bonus
            async with db.execute(
                "SELECT plan_type FROM investments WHERE id = ?", (investment_id,)
            ) as cursor:
                plan_row = await cursor.fetchone()
                plan_type = plan_row[0] if plan_row else 'daily'
            
            # Get plan details
            plan = await self.get_investment_plan(plan_type)
            base_percentage = plan['percentage'] if plan else Config.BASE_PERCENTAGE
            
            async with db.execute(
                "SELECT referral_bonus FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                referral_bonus = row[0] if row else 0.0
            
            # Calculate payout amount with bonus
            total_percentage = base_percentage + referral_bonus
            payout_amount = amount * (1 + total_percentage / 100)
            
            # Update investment
            final_payout_address = payout_address or sender_address
            await db.execute("""
                UPDATE investments SET 
                sender_address = ?, tx_hash = ?, payout_address = ?, 
                payout_amount = ?, status = 'confirmed'
                WHERE id = ?
            """, (sender_address, tx_hash, final_payout_address, payout_amount, investment_id))
            
            # Check if this is referrer's first investment
            async with db.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                referrer_id = row[0] if row else None
            
            if referrer_id:
                # Check if this is user's first investment
                async with db.execute(
                    "SELECT COUNT(*) FROM investments WHERE user_id = ? AND status = 'confirmed'",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    investment_count = row[0] if row else 0
                
                if investment_count == 1:  # First investment
                    # Update referrer's active referrals and bonus
                    await db.execute("""
                        UPDATE users SET 
                        active_referrals = active_referrals + 1,
                        referral_bonus = referral_bonus + ?
                        WHERE user_id = ?
                    """, (Config.REFERRAL_BONUS_PERCENTAGE, referrer_id))
            
            await db.commit()
            return True
    
    async def get_user_investments(self, user_id: int, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get user's investment history with pagination"""
        offset = (page - 1) * per_page
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get total count
            async with db.execute(
                "SELECT COUNT(*) FROM investments WHERE user_id = ?", (user_id,)
            ) as cursor:
                total_count = (await cursor.fetchone())[0]
            
            # Get paginated results
            async with db.execute("""
                SELECT * FROM investments 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, per_page, offset)) as cursor:
                rows = await cursor.fetchall()
                investments = [dict(row) for row in rows]
            
            total_pages = (total_count + per_page - 1) // per_page
            
            return {
                'investments': investments,
                'current_page': page,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
    
    async def get_pending_payouts(self) -> List[Dict[str, Any]]:
        """Get investments ready for payout"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM investments 
                WHERE status = 'confirmed' AND payout_date <= datetime('now')
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def mark_investment_paid(self, investment_id: int, payout_tx_hash: str):
        """Mark investment as paid"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE investments SET 
                status = 'paid', payout_tx_hash = ?
                WHERE id = ?
            """, (payout_tx_hash, investment_id))
            await db.commit()
    
    async def get_daily_stats(self, date: str = None) -> Dict[str, Any]:
        """Get daily statistics"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        async with aiosqlite.connect(self.db_path) as db:
            # New investors
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) FROM investments 
                WHERE date(created_at) = ? AND status != 'pending'
            """, (date,)) as cursor:
                new_investors = (await cursor.fetchone())[0]
            
            # Total investments
            async with db.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM investments 
                WHERE date(created_at) = ? AND status != 'pending'
            """, (date,)) as cursor:
                total_investments = (await cursor.fetchone())[0]
            
            # Total payouts
            async with db.execute("""
                SELECT COALESCE(SUM(payout_amount), 0) FROM investments 
                WHERE date(payout_date) = ? AND status = 'confirmed'
            """, (date,)) as cursor:
                total_payouts = (await cursor.fetchone())[0]
            
            profit = total_investments - total_payouts
            
            return {
                'new_investors': new_investors,
                'total_investments': total_investments,
                'total_payouts': total_payouts,
                'profit': profit
            }
    
    async def get_all_users(self) -> List[int]:
        """Get all user IDs"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting value"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default
    
    async def set_setting(self, key: str, value: str):
        """Set setting value"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """, (key, value))
            await db.commit()
    
    async def add_proxy_wallet(self, address: str, private_key: str):
        """Add proxy wallet to database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO proxy_wallets (address, private_key)
                VALUES (?, ?)
            """, (address, private_key))
            await db.commit()
    
    async def get_unused_proxy_wallet(self) -> Optional[Dict[str, str]]:
        """Get unused proxy wallet"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT address, private_key FROM proxy_wallets 
                WHERE is_used = FALSE 
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Mark as used
                    await db.execute(
                        "UPDATE proxy_wallets SET is_used = TRUE WHERE address = ?",
                        (row['address'],)
                    )
                    await db.commit()
                    return dict(row)
                return None

# Global database instance
db = Database()