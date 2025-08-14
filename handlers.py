import asyncio
import re
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config, TRANSLATIONS
from database import db
from blockchain import blockchain
from keyboards import (
    get_language_keyboard, get_main_menu_keyboard, get_back_keyboard,
    get_cancel_keyboard, get_payout_address_keyboard, get_admin_menu_keyboard,
    get_yes_no_keyboard
)

router = Router()

# States
class InvestmentStates(StatesGroup):
    waiting_amount = State()
    waiting_payment = State()
    waiting_payout_address = State()
    waiting_plan_selection = State()

class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_new_password = State()
    waiting_percentage = State()
    waiting_broadcast_message = State()

# Helper functions
def get_user_language(user_data):
    return user_data.get('language_code', 'ru') if user_data else 'ru'

def is_working_hours():
    current_hour = datetime.now().hour
    return Config.WORKING_HOURS_START <= current_hour < Config.WORKING_HOURS_END

# Start command
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    # Extract referrer ID from start parameter
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
        except ValueError:
            pass
    
    # Get or create user
    user_data = await db.get_user(message.from_user.id)
    
    if not user_data:
        # New user - show language selection
        await db.add_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            referrer_id=referrer_id
        )
        
        await message.answer(
            "🌐 Choose your language / Выберите язык:",
            reply_markup=get_language_keyboard()
        )
    else:
        # Existing user - show main menu
        lang = get_user_language(user_data)
        t = TRANSLATIONS[lang]
        
        # Send welcome message with dynamic variables
        welcome_text = t['welcome_message'].format(
            base_percentage=Config.BASE_PERCENTAGE,
            payout_period=Config.PAYOUT_DELAY_HOURS,
            start_hour=Config.WORKING_HOURS_START,
            end_hour=Config.WORKING_HOURS_END,
            min_amount=Config.MIN_INVESTMENT,
            max_amount=Config.MAX_INVESTMENT
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_main_menu_keyboard(lang),
            parse_mode='Markdown'
        )

# Language selection
@router.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    await db.update_user_language(callback.from_user.id, lang)
    
    t = TRANSLATIONS[lang]
    
    await callback.message.edit_text(t['language_set'])
    await callback.message.answer(
        t['welcome_message'],
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode='Markdown'
    )
    await callback.answer()

# Main menu handlers
@router.message(F.text.in_([TRANSLATIONS['ru']['investments'], TRANSLATIONS['en']['investments']]))
async def handle_investments(message: Message, state: FSMContext):
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    if not is_working_hours():
        await message.answer(
            t['bot_not_working'].format(
                start_hour=Config.WORKING_HOURS_START,
                end_hour=Config.WORKING_HOURS_END
            ),
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Check if master wallet has enough BNB for gas
    master_bnb_balance = blockchain.get_bnb_balance(Config.MASTER_WALLET_ADDRESS)
    if master_bnb_balance < Config.BNB_GAS_AMOUNT:
        await message.answer(
            f"❌ Сервис временно недоступен. Попробуйте позже.\n\n"
            f"💡 Администратор уведомлён о проблеме."
        )
        await state.clear()
        return
    
    # Show investment plans
    await show_investment_plans(message, lang)

async def show_investment_plans(message: Message, lang: str):
    """Show available investment plans"""
    plans = await db.get_investment_plans(active_only=False)
    
    plans_text = "💰 Выберите тариф инвестирования:\n\n"
    
    from keyboards import get_investment_plans_keyboard
    keyboard = get_investment_plans_keyboard(plans, lang)
    
    for plan in plans:
        if plan['is_active']:
            plans_text += f"📈 **{plan['name']}**\n"
            plans_text += f"💵 Сумма: {plan['min_amount']}-{plan['max_amount']} USDT\n"
            plans_text += f"📊 Процент: {plan['percentage']}%\n"
            plans_text += f"⏰ Срок: {plan['duration_days']} дн.\n"
            plans_text += f"📝 {plan['description']}\n\n"
        else:
            plans_text += f"🔒 **{plan['name']}** - {plan['description']}\n\n"
    
    await message.answer(
        plans_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.message(F.text.in_([TRANSLATIONS['ru']['my_investments'], TRANSLATIONS['en']['my_investments']]))
async def handle_my_investments(message: Message, state: FSMContext):
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Get first page
    await show_investments_page(message, 1, lang, t)

async def show_investments_page(message: Message, page: int, lang: str, t: dict):
    """Show investments page with pagination"""
    result = await db.get_user_investments(message.from_user.id, page, per_page=5)
    
    if result['total_count'] == 0:
        await message.answer(
            t['no_investments'],
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    history_text = f"📊 Страница {result['current_page']} из {result['total_pages']}\n"
    history_text += f"Всего инвестиций: {result['total_count']}\n\n"
    
    for inv in result['investments']:
        status = t['status_paid'] if inv['status'] == 'paid' else t['status_pending']
        date_str = datetime.fromisoformat(inv['created_at']).strftime('%d.%m.%Y %H:%M')
        
        history_text += t['investment_item'].format(
            amount=inv['amount'],
            payout_amount=inv['payout_amount'] or (inv['amount'] * 1.01),
            date=date_str,
            status=status
        )
    
    # Create pagination keyboard
    from keyboards import get_investments_pagination_keyboard
    keyboard = get_investments_pagination_keyboard(result, lang)
    
    await message.answer(
        t['investment_history'].format(history=history_text),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.message(F.text.in_([TRANSLATIONS['ru']['referral_system'], TRANSLATIONS['en']['referral_system']]))
async def handle_referral_system(message: Message):
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    bot_info = await message.bot.get_me()
    
    await message.answer(
        t['referral_info'].format(
            bot_username=bot_info.username,
            user_id=message.from_user.id,
            total_referrals=user_data.get('total_referrals', 0),
            active_referrals=user_data.get('active_referrals', 0),
            bonus_percentage=user_data.get('referral_bonus', 0.0)
        ),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode='Markdown'
    )

@router.message(F.text.in_([TRANSLATIONS['ru']['language'], TRANSLATIONS['en']['language']]))
async def handle_language_change(message: Message):
    await message.answer(
        "🌐 Choose your language / Выберите язык:",
        reply_markup=get_language_keyboard()
    )

# Investment flow
# Old amount handler removed - now using direct proxy wallet generation

async def monitor_payment_new(message: Message, state: FSMContext, investment_id: int, proxy_address: str, plan: dict):
    """Monitor payment for new logic without predefined amount"""
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Monitor for 20 minutes
    for minute in range(20):
        await asyncio.sleep(60)  # Wait 1 minute
        
        # Check for payment
        payment_result = await blockchain.monitor_proxy_wallet(
            proxy_address, plan['min_amount'], plan['max_amount']
        )
        
        if payment_result:
            # Payment received - update investment with actual amount
            actual_amount = payment_result['amount']
            
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute(
                    "UPDATE investments SET amount = ? WHERE id = ?",
                    (actual_amount, investment_id)
                )
                await conn.commit()
            
            # Update investment payment info
            await db.update_investment_payment(
                investment_id,
                payment_result['from_address'],
                payment_result['tx_hash']
            )
            
            # Log payment received
            from logger import transaction_logger
            await transaction_logger.log_payment_received(
                message.from_user.id,
                actual_amount,
                payment_result['from_address'],
                proxy_address,
                payment_result['tx_hash']
            )
            
            # Calculate payout amount
            user_data = await db.get_user(message.from_user.id)
            referral_bonus = user_data.get('referral_bonus', 0.0)
            total_percentage = plan['percentage'] + referral_bonus
            payout_amount = actual_amount * (1 + total_percentage / 100)
            
            # Update payout amount
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute(
                    "UPDATE investments SET payout_amount = ? WHERE id = ?",
                    (payout_amount, investment_id)
                )
                await conn.commit()
            
            # Ask for payout address
            await message.answer(
                t['payment_received'].format(
                    amount=actual_amount,
                    payout_amount=payout_amount
                ),
                reply_markup=get_payout_address_keyboard(lang),
                parse_mode='Markdown'
            )
            
            await state.set_state(InvestmentStates.waiting_payout_address)
            
            # Check for referral bonus
            if user_data.get('referrer_id'):
                result = await db.get_user_investments(message.from_user.id, 1, per_page=100)
                confirmed_investments = [inv for inv in result['investments'] if inv['status'] in ['confirmed', 'paid']]
                
                if len(confirmed_investments) == 1:  # First investment
                    referrer_data = await db.get_user(user_data['referrer_id'])
                    if referrer_data:
                        user_name = message.from_user.first_name
                        if message.from_user.last_name:
                            user_name += f" {message.from_user.last_name}"
                        
                        new_bonus = referrer_data.get('referral_bonus', 0.0) + Config.REFERRAL_BONUS_PERCENTAGE
                        new_percentage = Config.BASE_PERCENTAGE + new_bonus
                        
                        referral_message = f"🎉 У вас новый активный реферал!\n\n"
                        referral_message += f"👤 [{user_name}](tg://user?id={message.from_user.id})\n\n"
                        referral_message += f"💰 Теперь вы получаете {new_percentage:.1f}% вместо {Config.BASE_PERCENTAGE}%"
                        
                        try:
                            await message.bot.send_message(
                                user_data['referrer_id'],
                                referral_message,
                                parse_mode='Markdown'
                            )
                            
                            # Log referral bonus
                            await transaction_logger.log_referral_bonus(
                                user_data['referrer_id'], 
                                message.from_user.id, 
                                Config.REFERRAL_BONUS_PERCENTAGE
                            )
                        except:
                            pass
            return
        
        # Update waiting message every 5 minutes
        if minute % 5 == 0 and minute > 0:
            remaining_minutes = 20 - minute
            try:
                await message.edit_text(
                    t['waiting_payment'].format(
                        amount=f"{plan['min_amount']}-{plan['max_amount']}",
                        address=proxy_address,
                        minutes=remaining_minutes
                    ),
                    parse_mode='Markdown'
                )
            except:
                pass
    
    # Timeout
    await state.clear()
    await message.answer(
        t['payment_timeout'],
        reply_markup=get_main_menu_keyboard(lang)
    )

async def monitor_payment(message: Message, state: FSMContext, investment_id: int, amount: float, proxy_address: str):
    """Monitor payment for investment"""
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Monitor for payment
    payment_result = await blockchain.monitor_proxy_wallet(
        proxy_address, amount, Config.INVESTMENT_TIMEOUT_MINUTES
    )
    
    current_state = await state.get_state()
    if current_state != InvestmentStates.waiting_payment:
        return  # User cancelled or changed state
    
    if payment_result:
        # Payment received
        await db.update_investment_payment(
            investment_id,
            payment_result['from_address'],
            payment_result['tx_hash']
        )
        
        # Log payment received
        from logger import transaction_logger
        await transaction_logger.log_payment_received(
            message.from_user.id,
            amount,
            payment_result['from_address'],
            proxy_address,
            payment_result['tx_hash']
        )
        
        # Calculate payout amount
        user_data = await db.get_user(message.from_user.id)
        base_percentage = float(await db.get_setting('daily_percentage', Config.BASE_PERCENTAGE))
        total_percentage = base_percentage + user_data.get('referral_bonus', 0.0)
        payout_amount = amount * (1 + total_percentage / 100)
        
        await state.update_data(
            sender_address=payment_result['from_address'],
            payout_amount=payout_amount
        )
        
        await message.answer(
            t['payment_received'].format(
                amount=amount,
                payout_amount=payout_amount
            ),
            reply_markup=get_payout_address_keyboard(lang)
        )
        
        await state.set_state(InvestmentStates.waiting_payout_address)
        
        # Check for referral bonus
        if user_data.get('referrer_id'):
            # Check if this is first investment
            result = await db.get_user_investments(message.from_user.id, 1, per_page=100)
            confirmed_investments = [inv for inv in result['investments'] if inv['status'] in ['confirmed', 'paid']]
            
            if len(confirmed_investments) == 1:  # First investment
                referrer_data = await db.get_user(user_data['referrer_id'])
                if referrer_data:
                    referrer_lang = get_user_language(referrer_data)
                    referrer_t = TRANSLATIONS[referrer_lang]
                    
                    # Create clickable name
                    user_name = message.from_user.first_name
                    if message.from_user.last_name:
                        user_name += f" {message.from_user.last_name}"
                    
                    new_bonus = referrer_data.get('referral_bonus', 0.0) + Config.REFERRAL_BONUS_PERCENTAGE
                    new_percentage = Config.BASE_PERCENTAGE + new_bonus
                    
                    referral_message = f"🎉 У вас новый активный реферал!\n\n"
                    referral_message += f"👤 [{user_name}](tg://user?id={message.from_user.id})\n\n"
                    referral_message += f"💰 Теперь вы получаете {new_percentage:.1f}% вместо {Config.BASE_PERCENTAGE}%"
                    
                    try:
                        await message.bot.send_message(
                            user_data['referrer_id'],
                            referral_message,
                            parse_mode='Markdown'
                        )
                        
                        # Log referral bonus
                        from logger import transaction_logger
                        await transaction_logger.log_referral_bonus(
                            user_data['referrer_id'], 
                            message.from_user.id, 
                            Config.REFERRAL_BONUS_PERCENTAGE
                        )
                    except:
                        pass  # User might have blocked the bot
    else:
        # Payment timeout
        await message.answer(
            t['payment_timeout'],
            reply_markup=get_main_menu_keyboard(lang)
        )
        await state.clear()

@router.callback_query(F.data == "use_sender_address", StateFilter(InvestmentStates.waiting_payout_address))
async def use_sender_address(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Update investment with sender address as payout address
    await db.update_investment_payment(
        data['investment_id'],
        data['sender_address'],
        "",  # tx_hash already set
        data['sender_address']  # Use sender as payout address
    )
    
    payout_date = (datetime.now() + timedelta(hours=Config.PAYOUT_DELAY_HOURS)).strftime('%d.%m.%Y %H:%M')
    
    await callback.message.edit_text(
        t['investment_confirmed'].format(
            amount=data['amount'],
            payout_amount=data['payout_amount'],
            payout_date=payout_date,
            payout_address=data['sender_address']
        ),
        parse_mode='Markdown'
    )
    
    await callback.message.answer(
        t['main_menu'],
        reply_markup=get_main_menu_keyboard(lang)
    )
    
    await state.clear()
    await callback.answer()

@router.message(StateFilter(InvestmentStates.waiting_payout_address))
async def process_payout_address(message: Message, state: FSMContext):
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Check for cancel
    if message.text == t['cancel']:
        await state.clear()
        await message.answer(
            t['main_menu'],
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Validate address
    if not blockchain.is_valid_address(message.text):
        await message.answer(t['invalid_address'])
        return
    
    data = await state.get_data()
    
    # Update investment with custom payout address
    await db.update_investment_payment(
        data['investment_id'],
        data['sender_address'],
        "",  # tx_hash already set
        message.text  # Custom payout address
    )
    
    payout_date = (datetime.now() + timedelta(hours=Config.PAYOUT_DELAY_HOURS)).strftime('%d.%m.%Y %H:%M')
    
    await message.answer(
        t['investment_confirmed'].format(
            amount=data['amount'],
            payout_amount=data['payout_amount'],
            payout_date=payout_date,
            payout_address=message.text
        ),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode='Markdown'
    )
    
    await state.clear()

# Admin commands
@router.message(Command("whosyourdaddy"))
async def admin_login(message: Message, state: FSMContext):
    # Extract password from command
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return
    
    password = parts[1]
    admin_password = await db.get_setting('admin_password', Config.ADMIN_PASSWORD)
    
    if Config.is_admin(message.from_user.id) and password == admin_password:
        user_data = await db.get_user(message.from_user.id)
        lang = get_user_language(user_data) if user_data else 'ru'
        t = TRANSLATIONS[lang]
        
        admin_name = Config.get_admin_name(message.from_user.id)
        welcome_message = f"🔐 Добро пожаловать, {admin_name}!\n\n{t['admin_access_granted']}"
        
        await message.answer(
            welcome_message,
            reply_markup=get_admin_menu_keyboard(lang)
        )
    else:
        await message.answer("❌ Access denied")

# Back button handler
@router.message(F.text.in_([TRANSLATIONS['ru']['back'], TRANSLATIONS['en']['back']]))
async def handle_back(message: Message, state: FSMContext):
    await state.clear()
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    
    await message.answer(
        TRANSLATIONS[lang]['main_menu'],
        reply_markup=get_main_menu_keyboard(lang)
    )

# Pagination handlers
@router.callback_query(F.data.startswith("inv_page_"))
async def handle_investments_pagination(callback: CallbackQuery):
    if callback.data == "inv_page_info":
        await callback.answer()
        return
    
    page = int(callback.data.split("_")[2])
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    result = await db.get_user_investments(callback.from_user.id, page, per_page=5)
    
    history_text = f"📊 Страница {result['current_page']} из {result['total_pages']}\n"
    history_text += f"Всего инвестиций: {result['total_count']}\n\n"
    
    for inv in result['investments']:
        status = t['status_paid'] if inv['status'] == 'paid' else t['status_pending']
        date_str = datetime.fromisoformat(inv['created_at']).strftime('%d.%m.%Y %H:%M')
        
        history_text += t['investment_item'].format(
            amount=inv['amount'],
            payout_amount=inv['payout_amount'] or (inv['amount'] * 1.01),
            date=date_str,
            status=status
        )
    
    from keyboards import get_investments_pagination_keyboard
    keyboard = get_investments_pagination_keyboard(result, lang)
    
    await callback.message.edit_text(
        t['investment_history'].format(history=history_text),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

# Share handlers
@router.callback_query(F.data == "share_results")
async def handle_share_results(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    
    from keyboards import get_share_keyboard
    
    await callback.message.edit_text(
        "📤 Выберите способ поделиться результатами:",
        reply_markup=get_share_keyboard(lang)
    )
    await callback.answer()

@router.callback_query(F.data == "share_telegram")
async def handle_share_telegram(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    result = await db.get_user_investments(callback.from_user.id, 1, per_page=100)
    
    total_invested = sum(inv['amount'] for inv in result['investments'] if inv['status'] in ['confirmed', 'paid'])
    total_earned = sum(inv['payout_amount'] or 0 for inv in result['investments'] if inv['status'] == 'paid')
    profit = total_earned - total_invested if total_earned > 0 else 0
    
    bot_info = await callback.bot.get_me()
    share_text = f"💰 Мои результаты в @{bot_info.username}:\n\n"
    share_text += f"📈 Инвестировано: {total_invested:.2f} USDT\n"
    if total_earned > 0:
        share_text += f"💵 Получено: {total_earned:.2f} USDT\n"
        share_text += f"🎯 Прибыль: +{profit:.2f} USDT\n\n"
    share_text += f"🔗 Присоединяйся: https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    await callback.message.edit_text(
        f"📱 Отправьте это сообщение в любой чат:\n\n{share_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data="share_copy")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_investments")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "share_copy")
async def handle_share_copy(callback: CallbackQuery):
    await callback.answer("📋 Текст скопирован! Вставьте его в любой чат.", show_alert=True)

@router.callback_query(F.data == "back_to_investments")
async def handle_back_to_investments(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    result = await db.get_user_investments(callback.from_user.id, 1, per_page=5)
    
    history_text = f"📊 Страница {result['current_page']} из {result['total_pages']}\n"
    history_text += f"Всего инвестиций: {result['total_count']}\n\n"
    
    for inv in result['investments']:
        status = t['status_paid'] if inv['status'] == 'paid' else t['status_pending']
        date_str = datetime.fromisoformat(inv['created_at']).strftime('%d.%m.%Y %H:%M')
        
        history_text += t['investment_item'].format(
            amount=inv['amount'],
            payout_amount=inv['payout_amount'] or (inv['amount'] * 1.01),
            date=date_str,
            status=status
        )
    
    from keyboards import get_investments_pagination_keyboard
    keyboard = get_investments_pagination_keyboard(result, lang)
    
    await callback.message.edit_text(
        t['investment_history'].format(history=history_text),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

# Investment plan selection handlers
@router.callback_query(F.data.startswith("select_plan_"))
async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    plan_id = callback.data.split("_")[2]
    plan = await db.get_investment_plan(plan_id)
    
    if not plan or not plan['is_active']:
        await callback.answer("❌ Тариф недоступен", show_alert=True)
        return
    
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Check if master wallet has enough BNB for gas
    master_bnb_balance = blockchain.get_bnb_balance(Config.MASTER_WALLET_ADDRESS)
    if master_bnb_balance < Config.BNB_GAS_AMOUNT:
        await callback.answer("❌ Сервис временно недоступен. Попробуйте позже.", show_alert=True)
        return
    
    # Generate proxy wallet immediately
    proxy_wallet = await blockchain.get_proxy_wallet()
    if not proxy_wallet:
        await callback.answer("❌ Ошибка генерации кошелька. Попробуйте позже.", show_alert=True)
        return
    
    # Create investment record without amount (will be filled when payment received)
    investment_id = await db.create_investment(
        callback.from_user.id, 0, proxy_wallet['address'], plan_id
    )
    
    # Log investment creation
    from logger import transaction_logger
    await transaction_logger.log_investment_created(
        callback.from_user.id, 0, proxy_wallet['address']
    )
    
    # Store investment data
    await state.update_data(
        selected_plan=plan_id,
        investment_id=investment_id,
        proxy_address=proxy_wallet['address']
    )
    
    plan_info = f"📈 **Тариф: {plan['name']}**\n\n"
    plan_info += f"📊 Доходность: {plan['percentage']}% за {plan['duration_days']} дн.\n"
    plan_info += f"💵 Диапазон: {plan['min_amount']}-{plan['max_amount']} USDT\n\n"
    plan_info += f"💳 **Адрес для инвестиции:**\n`{proxy_wallet['address']}`\n\n"
    plan_info += f"📝 Отправьте любую сумму от {plan['min_amount']} до {plan['max_amount']} USDT (BEP20) на указанный адрес.\n"
    plan_info += f"⏰ Время ожидания: 20 минут\n\n"
    plan_info += f"💡 Выплата будет рассчитана автоматически на основе фактически отправленной суммы."
    
    await callback.message.edit_text(
        plan_info,
        parse_mode='Markdown'
    )
    
    await state.set_state(InvestmentStates.waiting_payment)
    
    # Start monitoring payment
    asyncio.create_task(monitor_payment_new(
        callback.message, state, investment_id, proxy_wallet['address'], plan
    ))
    
    await callback.answer()

@router.callback_query(F.data.startswith("plan_coming_soon_"))
async def handle_plan_coming_soon(callback: CallbackQuery):
    await callback.answer("🔒 Этот тариф скоро будет доступен!", show_alert=True)

@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu_callback(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    await callback.message.edit_text(
        t['main_menu']
    )
    
    await callback.message.answer(
        t['main_menu'],
        reply_markup=get_main_menu_keyboard(lang)
    )
    await callback.answer()

# Cancel handler
@router.message(F.text.in_([TRANSLATIONS['ru']['cancel'], TRANSLATIONS['en']['cancel']]))
async def handle_cancel(message: Message, state: FSMContext):
    await handle_back(message, state)