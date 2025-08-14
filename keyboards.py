from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import TRANSLATIONS

def get_language_keyboard():
    """Language selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")]
    ])
    return keyboard

def get_main_menu_keyboard(lang: str = 'ru'):
    """Main menu keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['investments'])],
            [KeyboardButton(text=t['my_investments']), KeyboardButton(text=t['referral_system'])],
            [KeyboardButton(text=t['language'])]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_back_keyboard(lang: str = 'ru'):
    """Back button keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['back'])]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_cancel_keyboard(lang: str = 'ru'):
    """Cancel button keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['cancel'])]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_payout_address_keyboard(lang: str = 'ru'):
    """Payout address selection keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['use_sender_address'], callback_data="use_sender_address")]
    ])
    return keyboard

def get_admin_menu_keyboard(lang: str = 'ru'):
    """Admin menu keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['daily_report'])],
            [KeyboardButton(text=t['payout_settings']), KeyboardButton(text=t['change_password'])],
            [KeyboardButton(text=t['broadcast_message'])],
            [KeyboardButton(text="📋 Выгрузить логи")],
            [KeyboardButton(text=t['back'])]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_yes_no_keyboard(lang: str = 'ru'):
    """Yes/No keyboard"""
    t = TRANSLATIONS[lang]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['yes'], callback_data="yes")],
        [InlineKeyboardButton(text=t['no'], callback_data="no")]
    ])
    return keyboard

def get_copy_keyboard(text: str, lang: str = 'ru'):
    """Keyboard with copy button"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Copy", callback_data=f"copy_{text}")]
    ])
    return keyboard

def get_investments_pagination_keyboard(result: dict, lang: str = 'ru'):
    """Keyboard for investments pagination"""
    t = TRANSLATIONS[lang]
    buttons = []
    
    # Navigation buttons
    nav_buttons = []
    if result['has_prev']:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"inv_page_{result['current_page'] - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(
        text=f"{result['current_page']}/{result['total_pages']}", 
        callback_data="inv_page_info"
    ))
    
    if result['has_next']:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"inv_page_{result['current_page'] + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Share button
    buttons.append([InlineKeyboardButton(text="📤 Поделиться результатами", callback_data="share_results")])
    
    # Back button
    buttons.append([InlineKeyboardButton(text=t['back'], callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_share_keyboard(lang: str = 'ru'):
    """Keyboard for sharing results"""
    t = TRANSLATIONS[lang]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Telegram", callback_data="share_telegram")],
        [InlineKeyboardButton(text="📋 Скопировать текст", callback_data="share_copy")],
        [InlineKeyboardButton(text=t['back'], callback_data="back_to_investments")]
    ])
    return keyboard

def get_investment_plans_keyboard(plans: list, lang: str = 'ru'):
    """Keyboard for investment plans selection"""
    t = TRANSLATIONS[lang]
    buttons = []
    
    for plan in plans:
        if plan['is_active']:
            button_text = f"📈 {plan['name']} ({plan['percentage']}%)"
            buttons.append([InlineKeyboardButton(
                text=button_text, 
                callback_data=f"select_plan_{plan['id']}"
            )])
        else:
            button_text = f"🔒 {plan['name']} (скоро)"
            buttons.append([InlineKeyboardButton(
                text=button_text, 
                callback_data=f"plan_coming_soon_{plan['id']}"
            )])
    
    # Back button
    buttons.append([InlineKeyboardButton(text=t['back'], callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)