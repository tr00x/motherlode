from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config, TRANSLATIONS
from database import db
from keyboards import (
    get_admin_menu_keyboard, get_main_menu_keyboard, get_yes_no_keyboard,
    get_cancel_keyboard
)
from logger import transaction_logger

router = Router()

# Admin States
class AdminStates(StatesGroup):
    waiting_new_password = State()
    waiting_percentage = State()
    waiting_broadcast_message = State()
    waiting_log_dates = State()

# Helper functions
def get_user_language(user_data):
    return user_data.get('language_code', 'ru') if user_data else 'ru'

def is_admin(user_id: int) -> bool:
    return Config.is_admin(user_id)

# Admin menu handlers
@router.message(F.text.in_([TRANSLATIONS['ru']['daily_report'], TRANSLATIONS['en']['daily_report']]))
async def handle_daily_report(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Get today's stats
    today = datetime.now().strftime('%Y-%m-%d')
    stats = await db.get_daily_stats(today)
    
    report_text = t['report_text'].format(
        date=datetime.now().strftime('%d.%m.%Y'),
        new_investors=stats['new_investors'],
        total_investments=stats['total_investments'],
        total_payouts=stats['total_payouts'],
        profit=stats['profit']
    )
    
    await message.answer(
        report_text,
        reply_markup=get_admin_menu_keyboard(lang)
    )
    
    # Ask about tomorrow's payouts
    await message.answer(
        t['will_payouts_tomorrow'],
        reply_markup=get_yes_no_keyboard(lang)
    )

@router.callback_query(F.data.in_(["yes", "no"]))
async def handle_payout_decision(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    
    user_data = await db.get_user(callback.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    payouts_enabled = callback.data == "yes"
    await db.set_setting('payouts_enabled', str(payouts_enabled).lower())
    
    await callback.message.edit_text(
        f"✅ Payouts {'enabled' if payouts_enabled else 'disabled'} for tomorrow"
    )
    
    # Ask for percentage
    await callback.message.answer(
        t['enter_percentage'],
        reply_markup=get_cancel_keyboard(lang)
    )
    
    await state.set_state(AdminStates.waiting_percentage)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_percentage))
async def process_percentage(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Check for cancel
    if message.text == t['cancel']:
        await state.clear()
        await message.answer(
            t['admin_menu'],
            reply_markup=get_admin_menu_keyboard(lang)
        )
        return
    
    try:
        percentage = float(message.text)
        if percentage < 0:
            await message.answer("❌ Percentage must be >= 0")
            return
        
        await db.set_setting('daily_percentage', str(percentage))
        
        await message.answer(
            t['settings_updated'],
            reply_markup=get_admin_menu_keyboard(lang)
        )
        
        await state.clear()
    
    except ValueError:
        await message.answer("❌ Invalid number format")

@router.message(F.text.in_([TRANSLATIONS['ru']['change_password'], TRANSLATIONS['en']['change_password']]))
async def handle_change_password(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    await message.answer(
        t['enter_new_password'],
        reply_markup=get_cancel_keyboard(lang)
    )
    
    await state.set_state(AdminStates.waiting_new_password)

@router.message(StateFilter(AdminStates.waiting_new_password))
async def process_new_password(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Check for cancel
    if message.text == t['cancel']:
        await state.clear()
        await message.answer(
            t['admin_menu'],
            reply_markup=get_admin_menu_keyboard(lang)
        )
        return
    
    new_password = message.text.strip()
    if len(new_password) < 6:
        await message.answer("❌ Password must be at least 6 characters")
        return
    
    await db.set_setting('admin_password', new_password)
    
    await message.answer(
        t['password_changed'],
        reply_markup=get_admin_menu_keyboard(lang)
    )
    
    await state.clear()

@router.message(F.text.in_([TRANSLATIONS['ru']['broadcast_message'], TRANSLATIONS['en']['broadcast_message']]))
async def handle_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    await message.answer(
        t['enter_broadcast_message'],
        reply_markup=get_cancel_keyboard(lang)
    )
    
    await state.set_state(AdminStates.waiting_broadcast_message)

@router.message(StateFilter(AdminStates.waiting_broadcast_message))
async def process_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    # Check for cancel
    if message.text == t['cancel']:
        await state.clear()
        await message.answer(
            t['admin_menu'],
            reply_markup=get_admin_menu_keyboard(lang)
        )
        return
    
    broadcast_text = message.text
    
    # Get all users
    all_users = await db.get_all_users()
    
    sent_count = 0
    for user_id in all_users:
        try:
            await message.bot.send_message(user_id, broadcast_text)
            sent_count += 1
        except Exception:
            # User might have blocked the bot or deleted account
            continue
    
    await message.answer(
        t['broadcast_sent'].format(count=sent_count),
        reply_markup=get_admin_menu_keyboard(lang)
    )
    
    await state.clear()

@router.message(F.text.in_([TRANSLATIONS['ru']['payout_settings'], TRANSLATIONS['en']['payout_settings']]))
async def handle_payout_settings(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    user_data = await db.get_user(message.from_user.id)
    lang = get_user_language(user_data)
    t = TRANSLATIONS[lang]
    
    payouts_enabled = await db.get_setting('payouts_enabled', 'true')
    daily_percentage = await db.get_setting('daily_percentage', str(Config.BASE_PERCENTAGE))
    
    # Check BNB status
    from blockchain import blockchain
    bnb_insufficient = await db.get_setting('bnb_insufficient', 'false')
    master_bnb_balance = blockchain.get_bnb_balance(Config.MASTER_WALLET_ADDRESS)
    
    settings_text = f"⚙️ Current Settings:\n\n"
    settings_text += f"💸 Payouts: {'✅ Enabled' if payouts_enabled.lower() == 'true' else '❌ Disabled'}\n"
    settings_text += f"📈 Daily percentage: {daily_percentage}%\n\n"
    
    # BNB Status
    settings_text += f"⛽ Gas Status:\n"
    if bnb_insufficient.lower() == 'true':
        current_balance = await db.get_setting('bnb_current_balance', '0')
        required_amount = await db.get_setting('bnb_required_amount', str(Config.BNB_GAS_AMOUNT))
        settings_text += f"🔴 INSUFFICIENT BNB!\n"
        settings_text += f"💰 Current: {current_balance} BNB\n"
        settings_text += f"💸 Required: {required_amount} BNB\n"
        settings_text += f"🚫 New investments suspended\n"
    else:
        settings_text += f"🟢 BNB Balance: {master_bnb_balance:.6f} BNB\n"
        settings_text += f"⚙️ Gas Amount: {Config.BNB_GAS_AMOUNT} BNB\n"
    
    await message.answer(
            settings_text,
            reply_markup=get_admin_menu_keyboard(lang)
        )

@router.message(F.text == "📋 Выгрузить логи")
async def handle_export_logs(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📋 Выгрузка логов\n\n"
        "Введите диапазон дат в формате:\n"
        "YYYY-MM-DD YYYY-MM-DD\n\n"
        "Например: 2024-01-01 2024-01-31\n"
        "Или просто дату: 2024-01-15\n"
        "Или 'all' для всех логов",
        reply_markup=get_cancel_keyboard('ru')
    )
    
    await state.set_state(AdminStates.waiting_log_dates)

@router.message(StateFilter(AdminStates.waiting_log_dates))
async def process_log_dates(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "🔧 Админ-панель",
            reply_markup=get_admin_menu_keyboard('ru')
        )
        return
    
    try:
        text = message.text.strip()
        start_date = None
        end_date = None
        
        if text.lower() == 'all':
            # Get all logs
            pass
        elif ' ' in text:
            # Date range
            dates = text.split()
            start_date = dates[0]
            end_date = dates[1]
        else:
            # Single date
            start_date = text
            end_date = text
        
        # Get logs
        logs = await transaction_logger.get_logs(start_date, end_date)
        
        if len(logs) > 4000:  # Telegram message limit
            # Split into multiple messages
            chunks = [logs[i:i+4000] for i in range(0, len(logs), 4000)]
            for i, chunk in enumerate(chunks):
                await message.answer(
                    f"📋 Логи (часть {i+1}/{len(chunks)}):\n\n```\n{chunk}\n```",
                    parse_mode='Markdown'
                )
        else:
            await message.answer(
                f"📋 Логи транзакций:\n\n```\n{logs}\n```",
                parse_mode='Markdown'
            )
        
        await message.answer(
            "✅ Логи выгружены",
            reply_markup=get_admin_menu_keyboard('ru')
        )
        
        await state.clear()
    
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при выгрузке логов: {str(e)}\n\n"
            "Проверьте формат даты (YYYY-MM-DD)"
        )
        
        # Log admin action
        await transaction_logger.log_admin_action(
            message.from_user.id,
            "EXPORT_LOGS",
            f"Requested logs for: {message.text}"
        )