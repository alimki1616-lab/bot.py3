import os
import logging
import asyncio
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
CHANNEL_USERNAME = '@DepositStarsBet'
DEPOSIT_POST_LINK = 'https://t.me/DepositStarsBet/2'
MIN_WITHDRAWAL = 15
MIN_GAMES_FOR_WITHDRAWAL = 5
REFERRAL_REWARD = 1
INITIAL_BALANCE = 2
MIN_BET = 1

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN تنظیم نشده! لطفاً در .env یا Railway تنظیم کنید.")

users_db = {}
games_db = []
withdrawals_db = []

# آمار کل سیستم
total_stars_earned = 0  # کل Stars کسب شده توسط کاربران
total_stars_lost = 0    # کل Stars از دست رفته توسط کاربران

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

WINNING_CONDITIONS = {
    "football": [3, 4, 5],
    "basketball": [4, 5],
    "dart": [6],
    "bowling": [6],
    "slot": [1, 22, 43, 64],
    "dice": [6]
}

GAME_GUIDE = {
    "football": "⚽ برای برد باید توپ وارد دروازه شود",
    "basketball": "🏀 برای برد باید توپ داخل سبد برود",
    "dart": "🎯 برای برد باید دارت به مرکز هدف بخورد",
    "bowling": "🎳 برای برد باید تمام پین‌ها بیفتند",
    "slot": "🎰 برای برد باید 3 نماد یکسان بیاید",
    "dice": "🎲 برای برد باید عدد 6 بیاید"
}

# گزینه‌های برداشت
WITHDRAWAL_OPTIONS = {
    "teddy": {"name": "🧸 تدی", "amount": 15},
    "flower": {"name": "🌹 گل", "amount": 25},
    "rocket": {"name": "🚀 موشک", "amount": 50}
}

def get_user(user_id: int):
    return users_db.get(user_id)

def create_user(user_id: int, username: str = None, referred_by: int = None):
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
    
    # فقط به کسی که دعوت کرده پاداش بده
    if referred_by and referred_by in users_db:
        users_db[referred_by]["balance"] += REFERRAL_REWARD
        users_db[referred_by]["referrals"].append(user_id)
    
    return users_db[user_id]

async def update_balance(user_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE, reason: str = None):
    global total_stars_earned, total_stars_lost
    
    if user_id in users_db:
        old_balance = users_db[user_id]["balance"]
        users_db[user_id]["balance"] += amount
        new_balance = users_db[user_id]["balance"]
        
        # به‌روزرسانی آمار کل سیستم
        if amount > 0:
            total_stars_earned += amount
        else:
            total_stars_lost += abs(amount)
        
        if amount > 0:
            notification_text = "╔═══════════════════╗\n"
            notification_text += "║  💎 افزایش موجودی  ║\n"
            notification_text += "╚═══════════════════╝\n\n"
            notification_text += f"📊 موجودی قبلی:\n"
            notification_text += f"   └─ {old_balance} ⭐\n\n"
            notification_text += f"✨ مبلغ دریافتی:\n"
            notification_text += f"   └─ +{amount} ⭐\n\n"
            notification_text += f"💰 موجودی جدید:\n"
            notification_text += f"   └─ {new_balance} ⭐\n\n"
            if reason:
                notification_text += f"━━━━━━━━━━━━━━━━━━\n"
                notification_text += f"💬 {reason}"
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=notification_text
                )
            except Exception as e:
                logger.error(f"خطا در ارسال اعلان به کاربر {user_id}: {e}")

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        return False

def get_main_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("⚽ فوتبال", callback_data="game_football"),
         InlineKeyboardButton("🏀 بسکتبال", callback_data="game_basketball")],
        [InlineKeyboardButton("🎯 دارت", callback_data="game_dart"),
         InlineKeyboardButton("🎳 بولینگ", callback_data="game_bowling")],
        [InlineKeyboardButton("🎰 اسلات", callback_data="game_slot"),
         InlineKeyboardButton("🎲 تاس", callback_data="game_dice")],
        [InlineKeyboardButton("💰 موجودی من", callback_data="balance"),
         InlineKeyboardButton("📊 آمار من", callback_data="stats")],
        [InlineKeyboardButton("💎 واریز", callback_data="deposit"),
         InlineKeyboardButton("💸 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("🎁 دعوت دوستان", callback_data="referral")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("👨‍💼 پنل مدیریت", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 آمار کاربران", callback_data="admin_users"),
         InlineKeyboardButton("🎮 بازی‌ها", callback_data="admin_games")],
        [InlineKeyboardButton("⭐ آمار Stars", callback_data="admin_stars_stats")],
        [InlineKeyboardButton("🔄 بازیابی آمار Stars", callback_data="admin_reset_stars_stats")],
        [InlineKeyboardButton("➕ افزایش موجودی", callback_data="admin_add_balance"),
         InlineKeyboardButton("➖ کاهش موجودی", callback_data="admin_reduce_balance")],
        [InlineKeyboardButton("🚫 بلاک", callback_data="admin_block"),
         InlineKeyboardButton("✅ آنبلاک", callback_data="admin_unblock")],
        [InlineKeyboardButton("📋 درخواست‌های برداشت", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 ارسال خصوصی", callback_data="admin_send_user")],
        [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bet_amount_keyboard():
    keyboard = [
        [InlineKeyboardButton("1 ⭐", callback_data="bet_1"),
         InlineKeyboardButton("5 ⭐", callback_data="bet_5"),
         InlineKeyboardButton("10 ⭐", callback_data="bet_10")],
        [InlineKeyboardButton("💰 مبلغ دلخواه", callback_data="bet_custom")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_withdrawal_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧸 تدی - 15 ⭐", callback_data="withdraw_teddy")],
        [InlineKeyboardButton("🌹 گل - 25 ⭐", callback_data="withdraw_flower")],
        [InlineKeyboardButton("🚀 موشک - 50 ⭐", callback_data="withdraw_rocket")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_only_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    referred_by = None
    if context.args and context.args[0].startswith('ref'):
        try:
            referred_by = int(context.args[0][3:])
        except:
            pass
    
    is_member = await check_channel_membership(user_id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("✅ عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
        keyboard.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_membership")])
        
        membership_text = "╔═══════════════════╗\n"
        membership_text += "║   🔐 عضویت لازم    ║\n"
        membership_text += "╚═══════════════════╝\n\n"
        membership_text += "⚠️ برای استفاده از ربات\n"
        membership_text += "ابتدا باید در کانال عضو شوید\n\n"
        membership_text += "━━━━━━━━━━━━━━━━━━\n"
        membership_text += f"📢 کانال ما:\n{CHANNEL_USERNAME}\n"
        membership_text += "━━━━━━━━━━━━━━━━━━\n\n"
        membership_text += "✨ بعد از عضویت، دکمه\n'🔄 بررسی عضویت' را بزنید"
        
        await update.message.reply_text(
            membership_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    user_data = get_user(user_id)
    if not user_data:
        user_data = create_user(user_id, username, referred_by)
        
        # اعلان به کسی که دعوت کرده
        if referred_by:
            try:
                referrer_username = f"@{username}" if username else f"User {user_id}"
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 تبریک! کاربر جدیدی با لینک شما عضو شد\n\n"
                         f"👤 کاربر: {referrer_username}\n"
                         f"💰 {REFERRAL_REWARD} ⭐ به موجودی شما اضافه شد"
                )
            except:
                pass
    
    welcome_text = "✨━━━━━━━━━━━━━━━━━━✨\n"
    welcome_text += "🎮  به دنیای هیجان خوش آمدید  🎮\n"
    welcome_text += "✨━━━━━━━━━━━━━━━━━━✨\n\n"
    welcome_text += f"👋 سلام {user.first_name} عزیز!\n"
    welcome_text += f"💎 کیف پول شما: {user_data['balance']} ⭐\n\n"
    welcome_text += "🎯 ━━━ بازی‌های هیجان‌انگیز ━━━ 🎯\n\n"
    welcome_text += "⚽ فوتبال | شوت به دروازه!\n"
    welcome_text += "🏀 بسکتبال | پرتاب طلایی!\n"
    welcome_text += "🎯 دارت | نشانه‌گیری دقیق!\n"
    welcome_text += "🎳 بولینگ | استرایک کامل!\n"
    welcome_text += "🎰 اسلات | شانس بزرگ!\n"
    welcome_text += "🎲 تاس | حدس شماره!\n\n"
    welcome_text += "🔥 آماده‌اید برای برد بزرگ؟ 🔥\n"
    welcome_text += "👇 یک بازی انتخاب کنید 👇"
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id == ADMIN_ID))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_stars_earned, total_stars_lost
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    user_data = get_user(user_id)
    if user_data and user_data.get('is_blocked', False) and user_id != ADMIN_ID:
        await query.edit_message_text("🚫 شما از استفاده از ربات مسدود شده‌اید.")
        return
    
    if data == "check_membership":
        is_member = await check_channel_membership(user_id, context)
        if is_member:
            user_data = get_user(user_id)
            if not user_data:
                create_user(user_id, query.from_user.username)
            await query.edit_message_text(
                "✅ عضویت شما تأیید شد!\n\n🎉 از دستور /start استفاده کنید."
            )
        else:
            await query.answer("❌ هنوز در کانال عضو نشده‌اید!", show_alert=True)
        return
    
    if data.startswith("game_"):
        game_type = data.split("_")[1]
        context.user_data['current_game'] = game_type
        
        game_guide = GAME_GUIDE.get(game_type, "")
        
        game_text = f"🎮 ━━━ {GAME_NAMES[game_type]} ━━━ 🎮\n\n"
        game_text += f"✨ {game_guide} ✨\n\n"
        game_text += "━━━━━━━━━━━━━━━━━━\n"
        game_text += "💰 چقدر می‌خوای شرط ببندی؟\n"
        game_text += "━━━━━━━━━━━━━━━━━━\n\n"
        game_text += f"📊 کیف پول: {user_data['balance']} ⭐\n"
        game_text += f"🎯 حداقل شرط: {MIN_BET} ⭐\n\n"
        game_text += "🔥 برد = ضربدر 2 شرط شما! 🔥"
        
        await query.edit_message_text(
            game_text,
            reply_markup=get_bet_amount_keyboard()
        )
        return
    
    if data.startswith("bet_"):
        if data == "bet_custom":
            context.user_data['waiting_for_custom_bet'] = True
            context.user_data['game_message_id'] = query.message.message_id
            
            custom_text = "╔═══════════════════╗\n"
            custom_text += "║  💰 مبلغ دلخواه   ║\n"
            custom_text += "╚═══════════════════╝\n\n"
            custom_text += f"📊 موجودی شما: {user_data['balance']} ⭐\n"
            custom_text += f"⚠️ حداقل شرط: {MIN_BET} ⭐\n\n"
            custom_text += "━━━━━━━━━━━━━━━━━━\n"
            custom_text += "💬 مبلغ را وارد کنید:"
            
            await query.edit_message_text(
                custom_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        bet_amount = int(data.split("_")[1])
        
        if user_data['balance'] < bet_amount:
            await query.answer("❌ موجودی کافی نیست!", show_alert=True)
            return
        
        game_type = context.user_data.get('current_game', 'football')
        
        # نمایش لودینگ
        loading_text = "⏳ ━━━━━━━━━━━━━━━━━━ ⏳\n"
        loading_text += f"   {GAME_NAMES[game_type]}   \n"
        loading_text += "⏳ ━━━━━━━━━━━━━━━━━━ ⏳\n\n"
        loading_text += "🎲 بازی در حال انجامه...\n\n"
        loading_text += "━━━━━━━━━━━━━━━━━━\n"
        loading_text += f"💰 شرط شما: {bet_amount} ⭐\n"
        loading_text += "━━━━━━━━━━━━━━━━━━\n\n"
        loading_text += "🤞 خدا خدا کن برنده شی! 🤞"
        
        await query.edit_message_text(loading_text)
        
        # ارسال dice
        game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
        dice_message = await context.bot.send_dice(
            chat_id=query.message.chat_id,
            emoji=game_emoji
        )
        
        # صبر برای انیمیشن dice
        await asyncio.sleep(4)
        
        dice_value = dice_message.dice.value
        win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
        
        if win:
            reward = bet_amount * 2
            await update_balance(user_id, reward, context, f"برد در {GAME_NAMES[game_type]}")
            
            result_text = "🎉 ━━━━━━━━━━━━━━━━━━ 🎉\n"
            result_text += "      🏆 برنده شدی! 🏆      \n"
            result_text += "🎉 ━━━━━━━━━━━━━━━━━━ 🎉\n\n"
            result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
            result_text += f"🎯 نتیجه: {dice_value}\n\n"
            result_text += "━━━━━━━━━━━━━━━━━━\n\n"
            result_text += f"💰 شرط شما: {bet_amount} ⭐\n"
            result_text += f"🎁 جایزه: {reward} ⭐\n\n"
            result_text += "━━━━━━━━━━━━━━━━━━\n"
            
            users_db[user_id]["total_wins"] += 1
            users_db[user_id]["games_played"] += 1
        else:
            await update_balance(user_id, -bet_amount, context)
            
            result_text = "😔 ━━━━━━━━━━━━━━━━━━ 😔\n"
            result_text += "      این دفعه نشد!      \n"
            result_text += "😔 ━━━━━━━━━━━━━━━━━━ 😔\n\n"
            result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
            result_text += f"🎯 نتیجه: {dice_value}\n\n"
            result_text += "━━━━━━━━━━━━━━━━━━\n\n"
            result_text += f"💸 از دست رفت: {bet_amount} ⭐\n\n"
            result_text += "💪 نا امید نشو!\n"
            result_text += "دفعه بعد می‌بری! 🔥\n\n"
            result_text += "━━━━━━━━━━━━━━━━━━\n"
            
            users_db[user_id]["total_losses"] += 1
            users_db[user_id]["games_played"] += 1
        
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
        
        updated_user = get_user(user_id)
        result_text += f"💰 موجودی جدید:\n"
        result_text += f"   └─ {updated_user['balance']} ⭐"
        
        # ویرایش پیام اصلی
        await query.edit_message_text(
            result_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "balance":
        balance_text = "💎 ━━━━━━━━━━━━━━━━━━ 💎\n"
        balance_text += "       کیف پول شما       \n"
        balance_text += "💎 ━━━━━━━━━━━━━━━━━━ 💎\n\n"
        balance_text += f"✨ موجودی فعلی شما:\n\n"
        balance_text += f"      🌟 {user_data['balance']} ⭐ 🌟\n\n"
        balance_text += "━━━━━━━━━━━━━━━━━━\n"
        balance_text += "🚀 راه‌های افزایش موجودی:\n"
        balance_text += "━━━━━━━━━━━━━━━━━━\n\n"
        balance_text += "🎮 برد در بازی‌ها\n"
        balance_text += "💎 واریز Stars\n"
        balance_text += "🎁 دعوت دوستان\n\n"
        balance_text += "💪 همین الان شروع کن!"
        
        await query.edit_message_text(
            balance_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "stats":
        win_rate = 0
        if user_data['games_played'] > 0:
            win_rate = (user_data['total_wins'] / user_data['games_played']) * 100
        
        stats_text = "📊 ━━━━━━━━━━━━━━━━━━ 📊\n"
        stats_text += "      آمار شما      \n"
        stats_text += "📊 ━━━━━━━━━━━━━━━━━━ 📊\n\n"
        stats_text += f"💰 کیف پول: {user_data['balance']} ⭐\n\n"
        stats_text += "🎮 ━━━ آمار بازی‌ها ━━━ 🎮\n\n"
        stats_text += f"🎯 کل بازی‌ها: {user_data['games_played']}\n"
        stats_text += f"✅ برد: {user_data['total_wins']} بازی\n"
        stats_text += f"❌ باخت: {user_data['total_losses']} بازی\n"
        stats_text += f"📈 نرخ برد: {win_rate:.1f}%\n\n"
        stats_text += "━━━━━━━━━━━━━━━━━━\n"
        stats_text += f"🎁 دعوت‌های موفق: {len(user_data.get('referrals', []))} نفر\n"
        stats_text += f"💎 درآمد دعوت: {len(user_data.get('referrals', []))*REFERRAL_REWARD} ⭐\n\n"
        stats_text += "🔥 به راه خود ادامه بده! 🔥"
        
        await query.edit_message_text(
            stats_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "deposit":
        deposit_text = "💎 ━━━━━━━━━━━━━━━━━━ 💎\n"
        deposit_text += "      واریز آسان Stars     \n"
        deposit_text += "💎 ━━━━━━━━━━━━━━━━━━ 💎\n\n"
        deposit_text += "✨ فقط 3 قدم تا افزایش موجودی! ✨\n\n"
        deposit_text += "━━━━━━━━━━━━━━━━━━\n\n"
        deposit_text += "1️⃣ روی دکمه زیر کلیک کن 👇\n\n"
        deposit_text += "2️⃣ روی پست Stars بزن ⭐\n"
        deposit_text += "   (هر ⭐ = 1 ⭐ موجودی)\n\n"
        deposit_text += "3️⃣ بات خودکار Stars رو\n"
        deposit_text += "   به حسابت اضافه می‌کنه! 🎉\n\n"
        deposit_text += "━━━━━━━━━━━━━━━━━━\n"
        deposit_text += f"🆔 شناسه شما: {user_id}\n"
        deposit_text += "━━━━━━━━━━━━━━━━━━\n\n"
        deposit_text += "⚡️ سریع و امن! ⚡️"
        
        keyboard = [
            [InlineKeyboardButton("💎 واریز Stars", url=DEPOSIT_POST_LINK)],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(
            deposit_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == "withdraw":
        if user_data['balance'] <= 0:
            error_text = "⚠️ ━━━━━━━━━━━━━━━━━━ ⚠️\n"
            error_text += "      موجودی ناکافی!      \n"
            error_text += "⚠️ ━━━━━━━━━━━━━━━━━━ ⚠️\n\n"
            error_text += "😕 متاسفانه موجودی کافی نیست!\n\n"
            error_text += "💡 راه‌حل‌ها:\n\n"
            error_text += "💎 واریز Stars\n"
            error_text += "🎮 بازی و برد\n"
            error_text += "🎁 دعوت دوستان\n\n"
            error_text += "🚀 همین الان شارژ کن!"
            
            await query.answer("❌ موجودی صفر است!", show_alert=True)
            await query.edit_message_text(
                error_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        if user_data['games_played'] < MIN_GAMES_FOR_WITHDRAWAL:
            remaining_games = MIN_GAMES_FOR_WITHDRAWAL - user_data['games_played']
            
            error_text = "🎮 ━━━━━━━━━━━━━━━━━━ 🎮\n"
            error_text += "    شرط برای برداشت!    \n"
            error_text += "🎮 ━━━━━━━━━━━━━━━━━━ 🎮\n\n"
            error_text += f"⚠️ برای برداشت باید حداقل\n"
            error_text += f"   {MIN_GAMES_FOR_WITHDRAWAL} بازی انجام بدی!\n\n"
            error_text += "━━━━━━━━━━━━━━━━━━\n"
            error_text += f"📊 بازی‌های تو: {user_data['games_played']}\n"
            error_text += f"⚡️ باقیمانده: {remaining_games} بازی\n"
            error_text += "━━━━━━━━━━━━━━━━━━\n\n"
            error_text += "🎯 بریم بازی کنیم! 🔥"
            
            await query.answer(f"❌ {remaining_games} بازی دیگر لازم است!", show_alert=True)
            await query.edit_message_text(
                error_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        withdraw_text = "💸 ━━━━━━━━━━━━━━━━━━ 💸\n"
        withdraw_text += "     برداشت جوایز     \n"
        withdraw_text += "💸 ━━━━━━━━━━━━━━━━━━ 💸\n\n"
        withdraw_text += f"💰 موجودی شما: {user_data['balance']} ⭐\n"
        withdraw_text += f"🎮 بازی‌های انجام شده: {user_data['games_played']}\n\n"
        withdraw_text += "🎁 ━━━ جوایز شگفت‌انگیز ━━━ 🎁\n\n"
        withdraw_text += "🧸 تدی - فقط 15 ⭐\n"
        withdraw_text += "🌹 گل رز - فقط 25 ⭐\n"
        withdraw_text += "🚀 موشک - فقط 50 ⭐\n\n"
        withdraw_text += "━━━━━━━━━━━━━━━━━━\n"
        withdraw_text += "✨ جایزه رو انتخاب کن! ✨"
        
        await query.edit_message_text(
            withdraw_text,
            reply_markup=get_withdrawal_keyboard()
        )
        return
    
    if data.startswith("withdraw_"):
        gift_type = data.split("_")[1]
        gift_data = WITHDRAWAL_OPTIONS.get(gift_type)
        
        if not gift_data:
            await query.answer("❌ گزینه نامعتبر!", show_alert=True)
            return
        
        required_amount = gift_data['amount']
        
        if user_data['balance'] < required_amount:
            shortage = required_amount - user_data['balance']
            await query.answer(f"❌ موجودی کافی نیست! {shortage} ⭐ کم دارید", show_alert=True)
            return
        
        # ذخیره اطلاعات برای دریافت آیدی
        context.user_data['withdrawal_gift'] = gift_type
        context.user_data['withdrawal_amount'] = required_amount
        context.user_data['waiting_for_withdrawal_id'] = True
        
        id_text = "╔═══════════════════╗\n"
        id_text += "║   📝 ارسال آیدی   ║\n"
        id_text += "╚═══════════════════╝\n\n"
        id_text += f"🎁 گزینه: {gift_data['name']}\n"
        id_text += f"💰 مبلغ: {required_amount} ⭐\n\n"
        id_text += "━━━━━━━━━━━━━━━━━━\n"
        id_text += "💬 لطفاً آیدی خود را برای\n"
        id_text += "واریز ارسال کنید:\n\n"
        id_text += "📝 مثال:\n@username\nیا\n123456789"
        
        await query.edit_message_text(
            id_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    if data == "referral":
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        referral_text = "🎁 ━━━━━━━━━━━━━━━━━━ 🎁\n"
        referral_text += "   دعوت دوستان = درآمد!   \n"
        referral_text += "🎁 ━━━━━━━━━━━━━━━━━━ 🎁\n\n"
        referral_text += f"✨ هر دوست = {REFERRAL_REWARD} ⭐ به کیف پول شما!\n\n"
        referral_text += "━━━━━━━━━━━━━━━━━━\n"
        referral_text += "🔗 لینک اختصاصی شما:\n"
        referral_text += "━━━━━━━━━━━━━━━━━━\n\n"
        referral_text += f"{referral_link}\n\n"
        referral_text += "📊 ━━━ آمار شما ━━━ 📊\n\n"
        referral_text += f"👥 دعوت‌های موفق: {len(user_data.get('referrals', []))} نفر\n"
        referral_text += f"💰 کل درآمد: {len(user_data.get('referrals', []))*REFERRAL_REWARD} ⭐\n\n"
        referral_text += "🚀 بیشتر دعوت کن، بیشتر ببر! 🚀"
        
        await query.edit_message_text(
            referral_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "support":
        context.user_data['waiting_for_support'] = True
        
        support_text = "📞 ━━━━━━━━━━━━━━━━━━ 📞\n"
        support_text += "      پشتیبانی 24/7      \n"
        support_text += "📞 ━━━━━━━━━━━━━━━━━━ 📞\n\n"
        support_text += "💬 سوال یا مشکلی داری?\n"
        support_text += "تیم ما آماده کمکه! 🤝\n\n"
        support_text += "━━━━━━━━━━━━━━━━━━\n\n"
        support_text += "✍️ پیامت رو بنویس و ارسال کن\n\n"
        support_text += "⚡️ مستقیم به ادمین می‌رسه!\n"
        support_text += "⏱ در اسرع وقت پاسخ می‌دیم"
        
        await query.edit_message_text(
            support_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    if data == "admin_panel" and user_id == ADMIN_ID:
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  👨‍💼 پنل مدیریت   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "⚙️ یک گزینه را انتخاب کنید"
        
        await query.edit_message_text(
            admin_text,
            reply_markup=get_admin_keyboard()
        )
        return
    
    if data == "admin_users" and user_id == ADMIN_ID:
        total_users = len(users_db)
        blocked_users = sum(1 for u in users_db.values() if u.get('is_blocked', False))
        total_games = len(games_db)
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  👥 آمار کاربران   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "━━━━━━━━━━━━━━━━━━\n"
        admin_text += f"📊 کل کاربران: {total_users}\n"
        admin_text += f"🚫 مسدود شده: {blocked_users}\n"
        admin_text += f"🎮 کل بازی‌ها: {total_games}\n"
        admin_text += "━━━━━━━━━━━━━━━━━━"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_stars_stats" and user_id == ADMIN_ID:
        total_balance = sum(u['balance'] for u in users_db.values())
        net_profit = total_stars_lost - total_stars_earned
        
        stars_text = "╔═══════════════════╗\n"
        stars_text += "║  ⭐ آمار Stars    ║\n"
        stars_text += "╚═══════════════════╝\n\n"
        stars_text += "━━━━━━━━━━━━━━━━━━\n"
        stars_text += "📊 آمار کلی سیستم:\n"
        stars_text += "━━━━━━━━━━━━━━━━━━\n\n"
        stars_text += f"✅ کل Stars کسب شده:\n"
        stars_text += f"   └─ {total_stars_earned} ⭐\n\n"
        stars_text += f"❌ کل Stars از دست رفته:\n"
        stars_text += f"   └─ {total_stars_lost} ⭐\n\n"
        stars_text += f"💎 سود خالص سیستم:\n"
        stars_text += f"   └─ {net_profit} ⭐\n\n"
        stars_text += f"💰 کل موجودی کاربران:\n"
        stars_text += f"   └─ {total_balance} ⭐\n\n"
        stars_text += "━━━━━━━━━━━━━━━━━━\n"
        
        # نمودار ساده
        if total_stars_earned + total_stars_lost > 0:
            earned_percent = (total_stars_earned / (total_stars_earned + total_stars_lost)) * 100
            lost_percent = 100 - earned_percent
            stars_text += f"📈 نمودار:\n"
            stars_text += f"   ✅ برد: {earned_percent:.1f}%\n"
            stars_text += f"   ❌ باخت: {lost_percent:.1f}%"
        
        await query.edit_message_text(stars_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_reset_stars_stats" and user_id == ADMIN_ID:
        # بازیابی آمار
        total_stars_earned = 0
        total_stars_lost = 0
        
        reset_text = "╔═══════════════════╗\n"
        reset_text += "║  🔄 بازیابی آمار  ║\n"
        reset_text += "╚═══════════════════╝\n\n"
        reset_text += "✅ آمار Stars با موفقیت\n"
        reset_text += "بازیابی شد!\n\n"
        reset_text += "━━━━━━━━━━━━━━━━━━\n"
        reset_text += "📊 آمار جدید:\n"
        reset_text += "━━━━━━━━━━━━━━━━━━\n\n"
        reset_text += "✅ کل Stars کسب شده: 0 ⭐\n"
        reset_text += "❌ کل Stars از دست رفته: 0 ⭐\n"
        reset_text += "💎 سود خالص سیستم: 0 ⭐"
        
        await query.edit_message_text(reset_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_games" and user_id == ADMIN_ID:
        recent_games = games_db[-10:] if len(games_db) > 10 else games_db
        
        games_text = "╔═══════════════════╗\n"
        games_text += "║  🎮 آخرین بازی‌ها  ║\n"
        games_text += "╚═══════════════════╝\n\n"
        
        for game in reversed(recent_games):
            result = "✅" if game['won'] else "❌"
            username = game.get('username', 'unknown')
            games_text += f"{result} @{username}\n"
            games_text += f"   {game['game_type']} │ {game['bet_amount']} ⭐\n"
            games_text += "━━━━━━━━━━━━━━━━━━\n"
        
        if not recent_games:
            games_text += "هیچ بازی‌ای ثبت نشده"
        
        await query.edit_message_text(games_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_add_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'add_balance'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  ➕ افزایش موجودی  ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر مبلغ\n\n"
        admin_text += "📝 مثال:\n123456789 100"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_reduce_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'reduce_balance'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  ➖ کاهش موجودی   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر مبلغ\n\n"
        admin_text += "📝 مثال:\n123456789 50"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_block" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'block_user'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║   🚫 بلاک کاربر    ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 ایدی کاربر را ارسال کنید:\n\n"
        admin_text += "📝 مثال:\n123456789"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_unblock" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'unblock_user'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  ✅ آنبلاک کاربر   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 ایدی کاربر را ارسال کنید:\n\n"
        admin_text += "📝 مثال:\n123456789"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_withdrawals" and user_id == ADMIN_ID:
        pending_withdrawals = [w for w in withdrawals_db if w.get('status') == 'pending']
        
        withdrawal_text = "╔═══════════════════╗\n"
        withdrawal_text += "║  📋 درخواست‌ها    ║\n"
        withdrawal_text += "╚═══════════════════╝\n\n"
        
        if not pending_withdrawals:
            withdrawal_text += "هیچ درخواستی وجود ندارد"
        else:
            for w in pending_withdrawals:
                gift_name = WITHDRAWAL_OPTIONS.get(w.get('gift_type', 'teddy'), {}).get('name', 'نامشخص')
                withdrawal_text += f"👤 {w['username']}\n"
                withdrawal_text += f"🆔 {w['user_id']}\n"
                withdrawal_text += f"🎁 {gift_name}\n"
                withdrawal_text += f"💰 {w['amount']} ⭐\n"
                withdrawal_text += f"📝 آیدی: {w['withdrawal_id']}\n"
                withdrawal_text += "━━━━━━━━━━━━━━━━━━\n"
        
        await query.edit_message_text(withdrawal_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'broadcast'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  📢 ارسال همگانی   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 پیام خود را ارسال کنید\n\n"
        admin_text += "⚡️ به تمام کاربران ارسال می‌شود"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_send_user" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'send_user'
        
        admin_text = "╔═══════════════════╗\n"
        admin_text += "║  💬 ارسال خصوصی   ║\n"
        admin_text += "╚═══════════════════╝\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر پیام\n\n"
        admin_text += "📝 مثال:\n123456789 سلام"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "back_to_main":
        context.user_data.clear()
        
        back_text = "╔═══════════════════╗\n"
        back_text += "║   🏠 منوی اصلی    ║\n"
        back_text += "╚═══════════════════╝"
        
        await query.edit_message_text(
            back_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # حذف سیستم + و - در گروه
    # chat_type = update.message.chat.type
    # if chat_type in ['group', 'supergroup'] and user_id == ADMIN_ID:
    #     ... (کد قبلی حذف شد)
    
    if context.user_data.get('waiting_for_custom_bet'):
        try:
            bet_amount = int(text.strip())
            
            if bet_amount < MIN_BET:
                error_text = f"❌ مبلغ باید حداقل {MIN_BET} ⭐ باشد!\n\n"
                error_text += "💬 دوباره وارد کنید:"
                
                await update.message.reply_text(error_text)
                return
            
            user_data = get_user(user_id)
            if user_data['balance'] < bet_amount:
                error_text = "❌ موجودی کافی نیست!\n\n"
                error_text += f"💰 موجودی: {user_data['balance']} ⭐\n"
                error_text += f"💎 درخواستی: {bet_amount} ⭐"
                
                await update.message.reply_text(error_text)
                return
            
            game_type = context.user_data.get('current_game', 'football')
            context.user_data['waiting_for_custom_bet'] = False
            
            # حذف پیام کاربر
            try:
                await update.message.delete()
            except:
                pass
            
            # ویرایش پیام قبلی با لودینگ
            game_message_id = context.user_data.get('game_message_id')
            if game_message_id:
                loading_text = "╔═══════════════════╗\n"
                loading_text += f"║  {GAME_NAMES[game_type]}  ║\n"
                loading_text += "╚═══════════════════╝\n\n"
                loading_text += "⏳ در حال انجام بازی...\n\n"
                loading_text += "━━━━━━━━━━━━━━━━━━\n"
                loading_text += f"💰 شرط: {bet_amount} ⭐\n"
                loading_text += "━━━━━━━━━━━━━━━━━━"
                
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=game_message_id,
                    text=loading_text
                )
            
            game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
            dice_message = await context.bot.send_dice(
                chat_id=update.message.chat_id,
                emoji=game_emoji
            )
            
            await asyncio.sleep(4)
            
            dice_value = dice_message.dice.value
            win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
            
            if win:
                reward = bet_amount * 2
                await update_balance(user_id, reward, context, f"برد در {GAME_NAMES[game_type]}")
                
                result_text = "╔═══════════════════╗\n"
                result_text += "║   🎉 برنده شدید!   ║\n"
                result_text += "╚═══════════════════╝\n\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n"
                result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
                result_text += f"🎯 نتیجه: {dice_value}\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n\n"
                result_text += f"💰 شرط: {bet_amount} ⭐\n"
                result_text += f"🎁 برد: {reward} ⭐\n\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n"
                
                users_db[user_id]["total_wins"] += 1
                users_db[user_id]["games_played"] += 1
            else:
                await update_balance(user_id, -bet_amount, context)
                
                result_text = "╔═══════════════════╗\n"
                result_text += "║    😔 باختید!     ║\n"
                result_text += "╚═══════════════════╝\n\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n"
                result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
                result_text += f"🎯 نتیجه: {dice_value}\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n\n"
                result_text += f"💸 باخت: {bet_amount} ⭐\n\n"
                result_text += "━━━━━━━━━━━━━━━━━━\n"
                
                users_db[user_id]["total_losses"] += 1
                users_db[user_id]["games_played"] += 1
            
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
            
            updated_user = get_user(user_id)
            result_text += f"💰 موجودی جدید:\n"
            result_text += f"   └─ {updated_user['balance']} ⭐"
            
            # ویرایش پیام اصلی
            if game_message_id:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=game_message_id,
                    text=result_text,
                    reply_markup=get_main_keyboard(user_id == ADMIN_ID)
                )
            else:
                await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=result_text,
                    reply_markup=get_main_keyboard(user_id == ADMIN_ID)
                )
            return
            
        except ValueError:
            await update.message.reply_text("❌ فقط عدد وارد کنید!\n\n📝 مثال: 25")
            return
    
    if context.user_data.get('waiting_for_withdrawal_id'):
        user_data = get_user(user_id)
        gift_type = context.user_data.get('withdrawal_gift')
        withdrawal_amount = context.user_data.get('withdrawal_amount')
        gift_data = WITHDRAWAL_OPTIONS.get(gift_type)
        
        # کسر موجودی
        users_db[user_id]['balance'] -= withdrawal_amount
        
        withdrawal_data = {
            "user_id": user_id,
            "username": update.effective_user.username,
            "amount": withdrawal_amount,
            "gift_type": gift_type,
            "gift_name": gift_data['name'],
            "withdrawal_id": text,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        withdrawals_db.append(withdrawal_data)
        
        try:
            admin_notif = "╔═══════════════════╗\n"
            admin_notif += "║  🔔 درخواست جدید   ║\n"
            admin_notif += "╚═══════════════════╝\n\n"
            admin_notif += f"👤 @{update.effective_user.username or 'بدون_یوزرنیم'}\n"
            admin_notif += f"🆔 {user_id}\n"
            admin_notif += f"🎁 {gift_data['name']}\n"
            admin_notif += f"💰 {withdrawal_amount} ⭐\n\n"
            admin_notif += f"━━━━━━━━━━━━━━━━━━\n"
            admin_notif += f"📝 آیدی واریز:\n{text}"
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notif
            )
        except:
            pass
        
        context.user_data['waiting_for_withdrawal_id'] = False
        context.user_data.pop('withdrawal_gift', None)
        context.user_data.pop('withdrawal_amount', None)
        
        success_text = "✅ ━━━━━━━━━━━━━━━━━━ ✅\n"
        success_text += "    درخواست ثبت شد!    \n"
        success_text += "✅ ━━━━━━━━━━━━━━━━━━ ✅\n\n"
        success_text += "🎉 درخواست برداشت ثبت شد!\n\n"
        success_text += f"💰 {withdrawal_amount} ⭐ از موجودی\n"
        success_text += "   کسر شد\n\n"
        success_text += "━━━━━━━━━━━━━━━━━━\n\n"
        success_text += "⏱ تیم ما داره بررسی می‌کنه\n"
        success_text += "🎁 به زودی هدیه ارسال می‌شه!\n\n"
        success_text += "💌 ممنون از صبرت!"
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if context.user_data.get('waiting_for_support'):
        try:
            support_notif = "╔═══════════════════╗\n"
            support_notif += "║   📞 پیام جدید    ║\n"
            support_notif += "╚═══════════════════╝\n\n"
            support_notif += f"👤 @{update.effective_user.username or 'بدون_یوزرنیم'}\n"
            support_notif += f"🆔 {user_id}\n\n"
            support_notif += f"━━━━━━━━━━━━━━━━━━\n"
            support_notif += f"💬 پیام:\n{text}"
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=support_notif
            )
            
            context.user_data['waiting_for_support'] = False
            
            success_text = "╔═══════════════════╗\n"
            success_text += "║   ✅ ارسال شد!    ║\n"
            success_text += "╚═══════════════════╝\n\n"
            success_text += "پیام شما به پشتیبانی\n"
            success_text += "ارسال شد\n\n"
            success_text += "━━━━━━━━━━━━━━━━━━\n"
            success_text += "⏳ به زودی پاسخ\n"
            success_text += "داده می‌شود"
            
            await update.message.reply_text(
                success_text,
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام پشتیبانی: {e}")
            await update.message.reply_text(
                "❌ خطا در ارسال. بعداً تلاش کنید",
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
        return
    
    if user_id == ADMIN_ID:
        admin_action = context.user_data.get('admin_action')
        
        if admin_action == 'add_balance':
            try:
                parts = text.strip().split()
                target_user_id = int(parts[0])
                amount = int(parts[1])
                
                await update_balance(target_user_id, amount, context, "افزایش توسط ادمین")
                
                success_text = "╔═══════════════════╗\n"
                success_text += "║   ✅ انجام شد!    ║\n"
                success_text += "╚═══════════════════╝\n\n"
                success_text += f"🆔 {target_user_id}\n"
                success_text += f"➕ {amount} ⭐"
                
                await update.message.reply_text(
                    success_text,
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789 100")
            return
        
        elif admin_action == 'reduce_balance':
            try:
                parts = text.strip().split()
                target_user_id = int(parts[0])
                amount = int(parts[1])
                
                await update_balance(target_user_id, -amount, context, "کاهش توسط ادمین")
                
                success_text = "╔═══════════════════╗\n"
                success_text += "║   ✅ انجام شد!    ║\n"
                success_text += "╚═══════════════════╝\n\n"
                success_text += f"🆔 {target_user_id}\n"
                success_text += f"➖ {amount} ⭐"
                
                await update.message.reply_text(
                    success_text,
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789 50")
            return
        
        elif admin_action == 'block_user':
            try:
                target_user_id = int(text.strip())
                if target_user_id in users_db:
                    users_db[target_user_id]['is_blocked'] = True
                    await update.message.reply_text(
                        f"✅ کاربر {target_user_id} مسدود شد",
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ کاربر پیدا نشد!")
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789")
            return
        
        elif admin_action == 'unblock_user':
            try:
                target_user_id = int(text.strip())
                if target_user_id in users_db:
                    users_db[target_user_id]['is_blocked'] = False
                    await update.message.reply_text(
                        f"✅ کاربر {target_user_id} آزاد شد",
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ کاربر پیدا نشد!")
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789")
            return
        
        elif admin_action == 'broadcast':
            success_count = 0
            fail_count = 0
            
            broadcast_msg = f"╔═══════════════════╗\n"
            broadcast_msg += f"║  📢 پیام مدیریت   ║\n"
            broadcast_msg += f"╚═══════════════════╝\n\n"
            broadcast_msg += text
            
            for uid in users_db.keys():
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=broadcast_msg
                    )
                    success_count += 1
                except:
                    fail_count += 1
            
            result_text = "╔═══════════════════╗\n"
            result_text += "║   ✅ ارسال شد!    ║\n"
            result_text += "╚═══════════════════╝\n\n"
            result_text += f"📊 موفق: {success_count}\n"
            result_text += f"❌ ناموفق: {fail_count}"
            
            await update.message.reply_text(
                result_text,
                reply_markup=get_admin_keyboard()
            )
            context.user_data['admin_action'] = None
            return
        
        elif admin_action == 'send_user':
            try:
                parts = text.strip().split(maxsplit=1)
                target_user_id = int(parts[0])
                message = parts[1]
                
                personal_msg = f"╔═══════════════════╗\n"
                personal_msg += f"║  📬 پیام مدیریت   ║\n"
                personal_msg += f"╚═══════════════════╝\n\n"
                personal_msg += message
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=personal_msg
                )
                
                await update.message.reply_text(
                    f"✅ پیام به {target_user_id} ارسال شد",
                    reply_markup=get_admin_keyboard()
                )
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789 سلام")
            return

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("ربات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
