import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import DiceEmoji
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# تنظیمات
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@GiftsChatt')
MIN_WITHDRAWAL = 100
MIN_GAMES_FOR_WITHDRAWAL = 5
REFERRAL_REWARD = 5
INITIAL_BALANCE = 10
MIN_BET = 5  # حداقل شرط

# بررسی وجود توکن
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN تنظیم نشده! لطفاً در .env یا Railway تنظیم کنید.")

# ذخیره داده‌ها در حافظه
users_db = {}
games_db = []
withdrawals_db = []

# تنظیم لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# نقشه بازی‌ها به Emoji های تلگرام
GAME_EMOJI_MAP = {
    "football": DiceEmoji.FOOTBALL,
    "basketball": DiceEmoji.BASKETBALL,
    "dart": DiceEmoji.DARTS,
    "bowling": DiceEmoji.BOWLING,
    "slot": DiceEmoji.SLOT_MACHINE,
    "dice": DiceEmoji.DICE
}

GAME_NAMES = {
    "football": "⚽ فوتبال",
    "basketball": "🏀 بسکتبال",
    "dart": "🎯 دارت",
    "bowling": "🎳 بولینگ",
    "slot": "🎰 اسلات",
    "dice": "🎲 تاس"
}

# شرایط برد برای هر بازی
WINNING_CONDITIONS = {
    "football": [3, 4, 5],
    "basketball": [4, 5],
    "dart": [6],
    "bowling": [6],
    "slot": [1, 22, 43, 64],
    "dice": [6]
}

# راهنمای برد برای هر بازی
GAME_GUIDE = {
    "football": "⚽ برای برد باید توپ وارد دروازه شود (3، 4 یا 5)",
    "basketball": "🏀 برای برد باید توپ داخل سبد برود (4 یا 5)",
    "dart": "🎯 برای برد باید دارت به مرکز هدف بخورد (6)",
    "bowling": "🎳 برای برد باید تمام پین‌ها بیفتند (6)",
    "slot": "🎰 برای برد باید 3 نماد یکسان بیاید (1، 22، 43 یا 64)",
    "dice": "🎲 برای برد باید عدد 6 بیاید"
}

# توابع کمکی
def get_user(user_id: int):
    """دریافت کاربر از حافظه"""
    return users_db.get(user_id)

def create_user(user_id: int, username: str = None, referred_by: int = None):
    """ایجاد کاربر جدید"""
    user_data = {
        "user_id": user_id,
        "username": username,
        "balance": INITIAL_BALANCE,
        "games_played": 0,
        "total_wins": 0,
        "total_losses": 0,
        "referred_by": referred_by,
        "referrals": [],
        "is_blocked": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat()
    }
    users_db[user_id] = user_data
    
    # پاداش رفرال
    if referred_by and referred_by in users_db:
        users_db[referred_by]["balance"] += REFERRAL_REWARD
        users_db[referred_by]["referrals"].append(user_id)
    
    return users_db[user_id]

async def update_balance(user_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE, reason: str = None):
    """بروزرسانی موجودی کاربر و ارسال اعلان"""
    if user_id in users_db:
        old_balance = users_db[user_id]["balance"]
        users_db[user_id]["balance"] += amount
        new_balance = users_db[user_id]["balance"]
        
        # ارسال اعلان به کاربر در صورت افزایش موجودی
        if amount > 0:
            notification_text = f"🔔 اعلان افزایش موجودی\n\n"
            notification_text += f"💰 موجودی قبلی: {old_balance} 🦮\n"
            notification_text += f"✅ مبلغ اضافه شده: +{amount} 🦮\n"
            notification_text += f"💎 موجودی جدید: {new_balance} 🦮\n\n"
            if reason:
                notification_text += f"📝 دلیل: {reason}"
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=notification_text
                )
            except Exception as e:
                logger.error(f"خطا در ارسال اعلان به کاربر {user_id}: {e}")

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        return False

# کیبوردها
def get_main_keyboard(is_admin=False):
    """کیبورد اصلی"""
    keyboard = [
        [InlineKeyboardButton("⚽ فوتبال", callback_data="game_football"),
         InlineKeyboardButton("🏀 بسکتبال", callback_data="game_basketball")],
        [InlineKeyboardButton("🎯 دارت", callback_data="game_dart"),
         InlineKeyboardButton("🎳 بولینگ", callback_data="game_bowling")],
        [InlineKeyboardButton("🎰 اسلات", callback_data="game_slot"),
         InlineKeyboardButton("🎲 تاس", callback_data="game_dice")],
        [InlineKeyboardButton("💰 موجودی من", callback_data="balance"),
         InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("💎 واریز Dogs", callback_data="deposit"),
         InlineKeyboardButton("💸 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("👥 دعوت دوستان", callback_data="referral"),
         InlineKeyboardButton("📞 پشتیبانی", callback_data="support")]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """کیبورد پنل مدیریت"""
    keyboard = [
        [InlineKeyboardButton("👥 آمار کاربران", callback_data="admin_users"),
         InlineKeyboardButton("🎮 نتایج بازی‌ها", callback_data="admin_games")],
        [InlineKeyboardButton("➕ افزایش موجودی", callback_data="admin_add_balance"),
         InlineKeyboardButton("➖ کاهش موجودی", callback_data="admin_reduce_balance")],
        [InlineKeyboardButton("🚫 بلاک کاربر", callback_data="admin_block"),
         InlineKeyboardButton("✅ آنبلاک کاربر", callback_data="admin_unblock")],
        [InlineKeyboardButton("📋 درخواست‌های برداشت", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 ارسال پیام به همه", callback_data="admin_broadcast"),
         InlineKeyboardButton("💬 ارسال به کاربر", callback_data="admin_send_user")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bet_amount_keyboard():
    """کیبورد انتخاب مبلغ شرط"""
    keyboard = [
        [InlineKeyboardButton("5 Dogs 🦮", callback_data="bet_5"),
         InlineKeyboardButton("10 Dogs 🦮", callback_data="bet_10")],
        [InlineKeyboardButton("20 Dogs 🦮", callback_data="bet_20"),
         InlineKeyboardButton("50 Dogs 🦮", callback_data="bet_50")],
        [InlineKeyboardButton("💰 مبلغ دلخواه", callback_data="bet_custom")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_only_keyboard():
    """کیبورد فقط با دکمه بازگشت"""
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

# هندلرها
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    # بررسی رفرال
    referred_by = None
    if context.args and context.args[0].startswith('ref'):
        try:
            referred_by = int(context.args[0][3:])
        except:
            pass
    
    # بررسی عضویت در کانال
    is_member = await check_channel_membership(user_id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("✅ عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
        keyboard.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_membership")])
        await update.message.reply_text(
            f"🔒 برای استفاده از ربات، ابتدا باید در کانال عضو شوید:\n\n{CHANNEL_USERNAME}\n\n✨ بعد از عضویت، دکمه 'بررسی عضویت' را بزنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی کاربر در حافظه
    user_data = get_user(user_id)
    if not user_data:
        user_data = create_user(user_id, username, referred_by)
        
        # اطلاع به رفرر
        if referred_by:
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 کاربر جدیدی با دعوت شما وارد شد!\n💰 {REFERRAL_REWARD} Dogs به موجودی شما اضافه شد."
                )
            except:
                pass
    
    welcome_text = f"""╔═══════════════════╗
║   🎮 خوش آمدید!    ║
╚═══════════════════╝

👤 کاربر: {user.first_name}
💰 موجودی: {user_data['balance']} 🦮

━━━━━━━━━━━━━━━━━━
🎯 بازی‌های موجود:

⚽ فوتبال | 🏀 بسکتبال
🎯 دارت   | 🎳 بولینگ
🎰 اسلات  | 🎲 تاس

━━━━━━━━━━━━━━━━━━
یک بازی انتخاب کنید! 🎲"""
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id == ADMIN_ID))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌های inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # بررسی بلاک بودن کاربر
    user_data = get_user(user_id)
    if user_data and user_data.get('is_blocked', False) and user_id != ADMIN_ID:
        await query.edit_message_text("🚫 شما از استفاده از ربات مسدود شده‌اید.")
        return
    
    # بررسی عضویت در کانال
    if data == "check_membership":
        is_member = await check_channel_membership(user_id, context)
        if is_member:
            user_data = get_user(user_id)
            if not user_data:
                create_user(user_id, query.from_user.username)
            await query.edit_message_text(
                "✅ عضویت شما تأیید شد!\n\nاز دستور /start استفاده کنید."
            )
        else:
            await query.answer("❌ هنوز در کانال عضو نشده‌اید!", show_alert=True)
        return
    
    # بازی‌ها
    if data.startswith("game_"):
        game_type = data.split("_")[1]
        context.user_data['current_game'] = game_type
        
        game_guide = GAME_GUIDE.get(game_type, "")
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🎮 بازی {GAME_NAMES[game_type]}\n\n{game_guide}\n\n💰 مبلغ شرط خود را انتخاب کنید:",
            reply_markup=get_bet_amount_keyboard()
        )
        return
    
    # شرط‌بندی
    if data.startswith("bet_"):
        if data == "bet_custom":
            context.user_data['waiting_for_custom_bet'] = True
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"💰 مبلغ شرط دلخواه\n\n💎 حداقل شرط: {MIN_BET} 🦮\n\nلطفاً مبلغ مورد نظر را وارد کنید:",
                reply_markup=get_back_only_keyboard()
            )
            return
        
        bet_amount = int(data.split("_")[1])
        
        if user_data['balance'] < bet_amount:
            await query.answer("❌ موجودی شما کافی نیست!", show_alert=True)
            return
        
        game_type = context.user_data.get('current_game', 'football')
        
        # ارسال بازی تلگرام
        game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
        dice_message = await context.bot.send_dice(
            chat_id=query.message.chat_id,
            emoji=game_emoji
        )
        
        dice_value = dice_message.dice.value
        
        # بررسی برد
        win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
        
        if win:
            reward = bet_amount * 2
            await update_balance(user_id, reward, context, f"برد در بازی {GAME_NAMES[game_type]}")
            result_emoji = "🎉"
            result_text = f"برنده شدید!\n💰 {reward} 🦮 به موجودی شما اضافه شد"
            users_db[user_id]["total_wins"] += 1
            users_db[user_id]["games_played"] += 1
        else:
            await update_balance(user_id, -bet_amount, context)
            result_emoji = "😔"
            result_text = f"باختید!\n💸 {bet_amount} 🦮 از موجودی شما کم شد"
            users_db[user_id]["total_losses"] += 1
            users_db[user_id]["games_played"] += 1
        
        # ذخیره نتیجه بازی
        game_record = {
            "user_id": user_id,
            "username": query.from_user.username,
            "game_type": game_type,
            "bet_amount": bet_amount,
            "dice_value": dice_value,
            "won": win,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        games_db.append(game_record)
        
        # دریافت موجودی جدید
        updated_user = get_user(user_id)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"{result_emoji} {result_text}\n\n💰 موجودی جدید: {updated_user['balance']} 🦮",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    # موجودی
    if data == "balance":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"💰 موجودی شما: {user_data['balance']} 🦮\n\n✨ برای افزایش موجودی می‌توانید واریز کنید یا دوستان خود را دعوت کنید!",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    # آمار
    if data == "stats":
        win_rate = 0
        if user_data['games_played'] > 0:
            win_rate = (user_data['total_wins'] / user_data['games_played']) * 100
        
        stats_text = f"""📊 آمار شما:

━━━━━━━━━━━━━━━━━━
💰 موجودی: {user_data['balance']} 🦮
🎮 تعداد بازی‌ها: {user_data['games_played']}
✅ برد: {user_data['total_wins']}
❌ باخت: {user_data['total_losses']}
📈 درصد برد: {win_rate:.1f}%
👥 تعداد دعوت‌شده‌ها: {len(user_data.get('referrals', []))}
━━━━━━━━━━━━━━━━━━"""
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=stats_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    # واریز
    if data == "deposit":
        deposit_text = f"""💎 واریز Dogs

لطفاً برای انتقال داگز از اولترا به والت ادمین عضو چنل بشوید:
{CHANNEL_USERNAME}

داگز را برای پیام پین شده انتقال بدید.
بعد از بررسی و صحت واریز به موجودی شما اضافه می‌شود.

🆔 شناسه شما: {user_id}"""
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=deposit_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    # برداشت
    if data == "withdraw":
        # بررسی موجودی صفر
        if user_data['balance'] <= 0:
            await query.answer(
                "❌ موجودی شما صفر است! ابتدا باید واریز کنید یا بازی کنید.",
                show_alert=True
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ موجودی شما صفر است!\n\n💎 برای شروع می‌توانید واریز کنید یا از موجودی اولیه استفاده کنید.",
                reply_markup=get_back_only_keyboard()
            )
            return
        
        # بررسی حداقل بازی
        if user_data['games_played'] < MIN_GAMES_FOR_WITHDRAWAL:
            remaining_games = MIN_GAMES_FOR_WITHDRAWAL - user_data['games_played']
            await query.answer(
                f"❌ برای برداشت باید حداقل {MIN_GAMES_FOR_WITHDRAWAL} بازی انجام دهید!\nشما {user_data['games_played']} بازی انجام داده‌اید. {remaining_games} بازی دیگر لازم است.",
                show_alert=True
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ شرط برداشت:\n\n🎮 حداقل {MIN_GAMES_FOR_WITHDRAWAL} بازی\n📊 بازی‌های شما: {user_data['games_played']}\n⚠️ باقیمانده: {remaining_games} بازی\n\nابتدا بازی کنید!",
                reply_markup=get_back_only_keyboard()
            )
            return
        
        # بررسی حداقل موجودی برای برداشت
        if user_data['balance'] < MIN_WITHDRAWAL:
            await query.answer(
                f"❌ موجودی شما کافی نیست!\nحداقل برداشت: {MIN_WITHDRAWAL} 🦮\nموجودی شما: {user_data['balance']} 🦮",
                show_alert=True
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ موجودی کافی نیست!\n\n━━━━━━━━━━━━━━━━━━\n💰 موجودی شما: {user_data['balance']} 🦮\n✅ حداقل برداشت: {MIN_WITHDRAWAL} 🦮\n⚠️ کمبود: {MIN_WITHDRAWAL - user_data['balance']} 🦮\n━━━━━━━━━━━━━━━━━━\n\nبرای افزایش موجودی بازی کنید یا واریز نمایید!",
                reply_markup=get_back_only_keyboard()
            )
            return
        
        withdraw_text = f"""💸 برداشت Dogs

━━━━━━━━━━━━━━━━━━
💰 موجودی شما: {user_data['balance']} 🦮
✅ حداقل برداشت: {MIN_WITHDRAWAL} 🦮
🎮 بازی‌های انجام شده: {user_data['games_played']}
━━━━━━━━━━━━━━━━━━

برای برداشت، نام کاربری @ و ایدی عددی خود را ارسال کنید:

مثال:
@username
123456789"""
        
        context.user_data['waiting_for_withdrawal'] = True
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=withdraw_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    # دعوت دوستان
    if data == "referral":
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        referral_text = f"""👥 دعوت دوستان

🎁 به ازای هر دعوت {REFERRAL_REWARD} 🦮 دریافت کنید!

━━━━━━━━━━━━━━━━━━
🔗 لینک دعوت شما:
{referral_link}

👥 تعداد دعوت‌های شما: {len(user_data.get('referrals', []))}
━━━━━━━━━━━━━━━━━━"""
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=referral_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    # پشتیبانی
    if data == "support":
        context.user_data['waiting_for_support'] = True
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📞 پشتیبانی\n\n💬 لطفاً پیام خود را برای پشتیبانی ارسال کنید:\n\nپیام شما به ادمین ارسال می‌شود.",
            reply_markup=get_back_only_keyboard()
        )
        return
    
    # پنل مدیریت
    if data == "admin_panel" and user_id == ADMIN_ID:
        await query.edit_message_text(
            "⚙️ پنل مدیریت\n\nیک گزینه را انتخاب کنید:",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # آمار کاربران (ادمین)
    if data == "admin_users" and user_id == ADMIN_ID:
        total_users = len(users_db)
        blocked_users = sum(1 for u in users_db.values() if u.get('is_blocked', False))
        total_games = len(games_db)
        
        admin_text = f"""👥 آمار کاربران:

━━━━━━━━━━━━━━━━━━
📊 تعداد کل کاربران: {total_users}
🚫 کاربران مسدود شده: {blocked_users}
🎮 تعداد کل بازی‌ها: {total_games}
━━━━━━━━━━━━━━━━━━"""
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    # نتایج بازی‌ها (ادمین)
    if data == "admin_games" and user_id == ADMIN_ID:
        recent_games = games_db[-10:] if len(games_db) > 10 else games_db
        
        games_text = "🎮 آخرین نتایج بازی‌ها:\n\n"
        for game in reversed(recent_games):
            result = "✅ برد" if game['won'] else "❌ باخت"
            username = game.get('username', 'unknown')
            games_text += f"👤 @{username}\n🎯 {game['game_type']} - {game['bet_amount']} 🦮 - {result}\n\n"
        
        if not recent_games:
            games_text = "هیچ بازی‌ای ثبت نشده است."
        
        await query.edit_message_text(games_text, reply_markup=get_admin_keyboard())
        return
    
    # افزایش موجودی (ادمین)
    if data == "admin_add_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'add_balance'
        await query.edit_message_text(
            "➕ افزایش موجودی\n\nلطفاً ایدی کاربر و مبلغ را ارسال کنید:\n\nمثال:\n123456789 100",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # کاهش موجودی (ادمین)
    if data == "admin_reduce_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'reduce_balance'
        await query.edit_message_text(
            "➖ کاهش موجودی\n\nلطفاً ایدی کاربر و مبلغ را ارسال کنید:\n\nمثال:\n123456789 50",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # بلاک کاربر (ادمین)
    if data == "admin_block" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'block_user'
        await query.edit_message_text(
            "🚫 بلاک کاربر\n\nلطفاً ایدی کاربر را ارسال کنید:\n\nمثال:\n123456789",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # آنبلاک کاربر (ادمین)
    if data == "admin_unblock" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'unblock_user'
        await query.edit_message_text(
            "✅ آنبلاک کاربر\n\nلطفاً ایدی کاربر را ارسال کنید:\n\nمثال:\n123456789",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # درخواست‌های برداشت (ادمین)
    if data == "admin_withdrawals" and user_id == ADMIN_ID:
        pending_withdrawals = [w for w in withdrawals_db if w.get('status') == 'pending']
        
        if not pending_withdrawals:
            await query.edit_message_text(
                "📋 هیچ درخواست برداشتی وجود ندارد.",
                reply_markup=get_admin_keyboard()
            )
            return
        
        withdrawal_text = "📋 درخواست‌های برداشت:\n\n"
        for w in pending_withdrawals:
            withdrawal_text += f"👤 {w['username']} (ID: {w['user_id']})\n💰 مبلغ: {w['amount']} 🦮\n\n"
        
        await query.edit_message_text(withdrawal_text, reply_markup=get_admin_keyboard())
        return
    
    # ارسال پیام به همه (ادمین)
    if data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'broadcast'
        await query.edit_message_text(
            "📢 ارسال پیام به همه کاربران\n\nلطفاً پیام خود را ارسال کنید:\n\nپیام به تمام کاربران ارسال می‌شود.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # ارسال پیام به کاربر (ادمین)
    if data == "admin_send_user" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'send_user'
        await query.edit_message_text(
            "💬 ارسال پیام به کاربر\n\nلطفاً ایدی کاربر و پیام را ارسال کنید:\n\nمثال:\n123456789 سلام، این یک پیام تست است.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # بازگشت به منوی اصلی
    if data == "back_to_main":
        # پاک کردن context
        context.user_data.clear()
        
        await query.edit_message_text(
            "🏠 منوی اصلی",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های متنی"""
    user_id = update.effective_user.id
    text = update.message.text
    chat_type = update.message.chat.type
    
    # دستور +/- در گروه (فقط ادمین)
    if chat_type in ['group', 'supergroup'] and user_id == ADMIN_ID:
        if update.message.reply_to_message:
            # بررسی اینکه پیام با + یا - شروع شود
            if text.startswith('+') or text.startswith('-'):
                try:
                    amount = int(text)
                    target_user_id = update.message.reply_to_message.from_user.id
                    target_username = update.message.reply_to_message.from_user.username
                    
                    # بررسی وجود کاربر
                    if target_user_id not in users_db:
                        create_user(target_user_id, target_username)
                    
                    # بروزرسانی موجودی
                    if amount > 0:
                        reason = "افزایش توسط ادمین در گروه"
                    else:
                        reason = "کاهش توسط ادمین در گروه"
                    
                    await update_balance(target_user_id, amount, context, reason)
                    
                    new_balance = users_db[target_user_id]['balance']
                    
                    await update.message.reply_text(
                        f"✅ موجودی کاربر @{target_username or target_user_id} تغییر کرد\n\n"
                        f"{'➕' if amount > 0 else '➖'} {abs(amount)} 🦮\n"
                        f"💰 موجودی جدید: {new_balance} 🦮"
                    )
                    return
                except ValueError:
                    await update.message.reply_text("❌ فرمت نادرست! مثال: +100 یا -50")
                    return
                except Exception as e:
                    logger.error(f"خطا در تغییر موجودی: {e}")
                    await update.message.reply_text(f"❌ خطا: {str(e)}")
                    return
    
    # بررسی درخواست شرط دلخواه
    if context.user_data.get('waiting_for_custom_bet'):
        try:
            bet_amount = int(text.strip())
            
            if bet_amount < MIN_BET:
                await update.message.reply_text(
                    f"❌ مبلغ شرط باید حداقل {MIN_BET} 🦮 باشد!\n\nدوباره تلاش کنید:",
                    reply_markup=get_back_only_keyboard()
                )
                return
            
            user_data = get_user(user_id)
            if user_data['balance'] < bet_amount:
                await update.message.reply_text(
                    f"❌ موجودی شما کافی نیست!\n\n💰 موجودی شما: {user_data['balance']} 🦮\n💎 مبلغ درخواستی: {bet_amount} 🦮",
                    reply_markup=get_back_only_keyboard()
                )
                return
            
            # انجام بازی
            game_type = context.user_data.get('current_game', 'football')
            context.user_data['waiting_for_custom_bet'] = False
            
            # ارسال بازی تلگرام
            game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
            dice_message = await context.bot.send_dice(
                chat_id=update.message.chat_id,
                emoji=game_emoji
            )
            
            dice_value = dice_message.dice.value
            
            # بررسی برد
            win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
            
            if win:
                reward = bet_amount * 2
                await update_balance(user_id, reward, context, f"برد در بازی {GAME_NAMES[game_type]}")
                result_emoji = "🎉"
                result_text = f"برنده شدید!\n💰 {reward} 🦮 به موجودی شما اضافه شد"
                users_db[user_id]["total_wins"] += 1
                users_db[user_id]["games_played"] += 1
            else:
                await update_balance(user_id, -bet_amount, context)
                result_emoji = "😔"
                result_text = f"باختید!\n💸 {bet_amount} 🦮 از موجودی شما کم شد"
                users_db[user_id]["total_losses"] += 1
                users_db[user_id]["games_played"] += 1
            
            # ذخیره نتیجه بازی
            game_record = {
                "user_id": user_id,
                "username": update.effective_user.username,
                "game_type": game_type,
                "bet_amount": bet_amount,
                "dice_value": dice_value,
                "won": win,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            games_db.append(game_record)
            
            # دریافت موجودی جدید
            updated_user = get_user(user_id)
            
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"{result_emoji} {result_text}\n\n💰 موجودی جدید: {updated_user['balance']} 🦮",
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
            return
            
        except ValueError:
            await update.message.reply_text(
                "❌ لطفاً فقط عدد وارد کنید!\n\nمثال: 25",
                reply_markup=get_back_only_keyboard()
            )
            return
    
    # بررسی درخواست برداشت
    if context.user_data.get('waiting_for_withdrawal'):
        user_data = get_user(user_id)
        
        # ذخیره درخواست برداشت
        withdrawal_data = {
            "user_id": user_id,
            "username": update.effective_user.username,
            "amount": user_data['balance'],
            "withdrawal_info": text,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        withdrawals_db.append(withdrawal_data)
        
        # اطلاع به ادمین
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 درخواست برداشت جدید\n\n👤 کاربر: @{update.effective_user.username}\n🆔 ID: {user_id}\n💰 مبلغ: {user_data['balance']} 🦮\n\n📝 اطلاعات:\n{text}"
            )
        except:
            pass
        
        context.user_data['waiting_for_withdrawal'] = False
        await update.message.reply_text(
            "✅ درخواست برداشت شما ثبت شد.\nبعد از بررسی، Dogs به حساب شما واریز می‌شود.",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    # بررسی پیام پشتیبانی
    if context.user_data.get('waiting_for_support'):
        # ارسال پیام به ادمین
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📞 پیام پشتیبانی جدید\n\n👤 از: @{update.effective_user.username}\n🆔 ID: {user_id}\n\n💬 پیام:\n{text}"
            )
            
            context.user_data['waiting_for_support'] = False
            await update.message.reply_text(
                "✅ پیام شما به پشتیبانی ارسال شد.\n\nبه زودی پاسخ داده می‌شود.",
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام پشتیبانی: {e}")
            await update.message.reply_text(
                "❌ خطا در ارسال پیام. لطفاً بعداً تلاش کنید.",
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
        return
    
    # بررسی دستورات ادمین
    if user_id == ADMIN_ID:
        admin_action = context.user_data.get('admin_action')
        
        if admin_action == 'add_balance':
            try:
                parts = text.strip().split()
                target_user_id = int(parts[0])
                amount = int(parts[1])
                
                await update_balance(target_user_id, amount, context, "افزایش موجودی توسط ادمین")
                await update.message.reply_text(
                    f"✅ {amount} 🦮 به حساب کاربر {target_user_id} اضافه شد.",
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست! مثال: 123456789 100")
            return
        
        elif admin_action == 'reduce_balance':
            try:
                parts = text.strip().split()
                target_user_id = int(parts[0])
                amount = int(parts[1])
                
                await update_balance(target_user_id, -amount, context, "کاهش موجودی توسط ادمین")
                await update.message.reply_text(
                    f"✅ {amount} 🦮 از حساب کاربر {target_user_id} کم شد.",
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست! مثال: 123456789 50")
            return
        
        elif admin_action == 'block_user':
            try:
                target_user_id = int(text.strip())
                if target_user_id in users_db:
                    users_db[target_user_id]['is_blocked'] = True
                    await update.message.reply_text(
                        f"✅ کاربر {target_user_id} مسدود شد.",
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ کاربر پیدا نشد!")
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست! مثال: 123456789")
            return
        
        elif admin_action == 'unblock_user':
            try:
                target_user_id = int(text.strip())
                if target_user_id in users_db:
                    users_db[target_user_id]['is_blocked'] = False
                    await update.message.reply_text(
                        f"✅ کاربر {target_user_id} آزاد شد.",
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ کاربر پیدا نشد!")
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست! مثال: 123456789")
            return
        
        elif admin_action == 'broadcast':
            # ارسال پیام به همه کاربران
            success_count = 0
            fail_count = 0
            
            for uid in users_db.keys():
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📢 پیام از مدیریت:\n\n{text}"
                    )
                    success_count += 1
                except:
                    fail_count += 1
            
            await update.message.reply_text(
                f"✅ پیام ارسال شد\n\n📊 موفق: {success_count}\n❌ ناموفق: {fail_count}",
                reply_markup=get_admin_keyboard()
            )
            context.user_data['admin_action'] = None
            return
        
        elif admin_action == 'send_user':
            try:
                parts = text.strip().split(maxsplit=1)
                target_user_id = int(parts[0])
                message = parts[1]
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📬 پیام از مدیریت:\n\n{message}"
                )
                
                await update.message.reply_text(
                    f"✅ پیام به کاربر {target_user_id} ارسال شد.",
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست! مثال: 123456789 سلام")
            return

def main():
    """تابع اصلی"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # شروع ربات
    logger.info("ربات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
