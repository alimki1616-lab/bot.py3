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
MIN_BET = 5

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN تنظیم نشده! لطفاً در .env یا Railway تنظیم کنید.")

users_db = {}
games_db = []
withdrawals_db = []

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
    "football": "⚽ برای برد باید توپ وارد دروازه شود\n🎯 نتیجه برنده: 3، 4 یا 5",
    "basketball": "🏀 برای برد باید توپ داخل سبد برود\n🎯 نتیجه برنده: 4 یا 5",
    "dart": "🎯 برای برد باید دارت به مرکز هدف بخورد\n🎯 نتیجه برنده: 6",
    "bowling": "🎳 برای برد باید تمام پین‌ها بیفتند\n🎯 نتیجه برنده: 6",
    "slot": "🎰 برای برد باید 3 نماد یکسان بیاید\n🎯 نتیجه برنده: 1، 22، 43 یا 64",
    "dice": "🎲 برای برد باید عدد 6 بیاید\n🎯 نتیجه برنده: 6"
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
    
    if referred_by and referred_by in users_db:
        users_db[referred_by]["balance"] += REFERRAL_REWARD
        users_db[referred_by]["referrals"].append(user_id)
    
    return users_db[user_id]

async def update_balance(user_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE, reason: str = None):
    if user_id in users_db:
        old_balance = users_db[user_id]["balance"]
        users_db[user_id]["balance"] += amount
        new_balance = users_db[user_id]["balance"]
        
        if amount > 0:
            notification_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            notification_text += "┃  🔔 افزایش موجودی  ┃\n"
            notification_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            notification_text += f"📊 موجودی قبلی\n├─ {old_balance} 🦮\n\n"
            notification_text += f"✅ مبلغ دریافتی\n├─ +{amount} 🦮\n\n"
            notification_text += f"💎 موجودی جدید\n└─ {new_balance} 🦮\n\n"
            if reason:
                notification_text += f"💬 دلیل: {reason}"
            
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
        [InlineKeyboardButton("5 🦮", callback_data="bet_5"),
         InlineKeyboardButton("10 🦮", callback_data="bet_10"),
         InlineKeyboardButton("20 🦮", callback_data="bet_20")],
        [InlineKeyboardButton("50 🦮", callback_data="bet_50"),
         InlineKeyboardButton("💰 مبلغ دلخواه", callback_data="bet_custom")],
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
        
        membership_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        membership_text += "┃   🔐 عضویت لازم   ┃\n"
        membership_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        membership_text += "برای استفاده از ربات، ابتدا باید در کانال عضو شوید:\n\n"
        membership_text += f"📢 {CHANNEL_USERNAME}\n\n"
        membership_text += "✨ بعد از عضویت، دکمه 'بررسی عضویت' را بزنید."
        
        await update.message.reply_text(
            membership_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    user_data = get_user(user_id)
    if not user_data:
        user_data = create_user(user_id, username, referred_by)
        
        if referred_by:
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 تبریک! کاربر جدیدی با لینک شما عضو شد\n\n💰 {REFERRAL_REWARD} 🦮 به موجودی شما اضافه شد"
                )
            except:
                pass
    
    welcome_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
    welcome_text += "┃   🎮 خوش آمدید!   ┃\n"
    welcome_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
    welcome_text += f"👤 {user.first_name}\n"
    welcome_text += f"💰 موجودی: {user_data['balance']} 🦮\n\n"
    welcome_text += "┌─ 🎯 بازی‌های موجود\n"
    welcome_text += "│\n"
    welcome_text += "├─ ⚽ فوتبال  🏀 بسکتبال\n"
    welcome_text += "├─ 🎯 دارت    🎳 بولینگ\n"
    welcome_text += "└─ 🎰 اسلات   🎲 تاس\n\n"
    welcome_text += "🎲 یک بازی انتخاب کنید و شروع کنید!"
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id == ADMIN_ID))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        game_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        game_text += f"┃  {GAME_NAMES[game_type]}  ┃\n"
        game_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        game_text += f"{game_guide}\n\n"
        game_text += "┌─ 💰 انتخاب مبلغ شرط\n"
        game_text += "│\n"
        game_text += f"├─ حداقل: {MIN_BET} 🦮\n"
        game_text += f"└─ موجودی شما: {user_data['balance']} 🦮"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=game_text,
            reply_markup=get_bet_amount_keyboard()
        )
        return
    
    if data.startswith("bet_"):
        if data == "bet_custom":
            context.user_data['waiting_for_custom_bet'] = True
            
            custom_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            custom_text += "┃  💰 مبلغ دلخواه  ┃\n"
            custom_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            custom_text += f"📊 موجودی شما: {user_data['balance']} 🦮\n"
            custom_text += f"⚠️ حداقل شرط: {MIN_BET} 🦮\n\n"
            custom_text += "💬 مبلغ مورد نظر خود را وارد کنید:"
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=custom_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        bet_amount = int(data.split("_")[1])
        
        if user_data['balance'] < bet_amount:
            await query.answer("❌ موجودی کافی نیست!", show_alert=True)
            return
        
        game_type = context.user_data.get('current_game', 'football')
        
        game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
        dice_message = await context.bot.send_dice(
            chat_id=query.message.chat_id,
            emoji=game_emoji
        )
        
        dice_value = dice_message.dice.value
        win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
        
        if win:
            reward = bet_amount * 2
            await update_balance(user_id, reward, context, f"برد در {GAME_NAMES[game_type]}")
            
            result_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            result_text += "┃   🎉 برنده شدید!   ┃\n"
            result_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
            result_text += f"🎯 نتیجه: {dice_value}\n"
            result_text += f"💰 شرط: {bet_amount} 🦮\n"
            result_text += f"🎁 برد: {reward} 🦮\n\n"
            
            users_db[user_id]["total_wins"] += 1
            users_db[user_id]["games_played"] += 1
        else:
            await update_balance(user_id, -bet_amount, context)
            
            result_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            result_text += "┃    😔 باختید!     ┃\n"
            result_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            result_text += f"🎮 بازی: {GAME_NAMES[game_type]}\n"
            result_text += f"🎯 نتیجه: {dice_value}\n"
            result_text += f"💸 باخت: {bet_amount} 🦮\n\n"
            
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
        result_text += f"💰 موجودی جدید: {updated_user['balance']} 🦮"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=result_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "balance":
        balance_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        balance_text += "┃   💰 موجودی من   ┃\n"
        balance_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        balance_text += f"💎 موجودی فعلی\n"
        balance_text += f"└─ {user_data['balance']} 🦮\n\n"
        balance_text += "┌─ 📈 راه‌های افزایش موجودی\n"
        balance_text += "│\n"
        balance_text += "├─ 🎮 بازی کردن و برنده شدن\n"
        balance_text += "├─ 💎 واریز مستقیم\n"
        balance_text += "└─ 🎁 دعوت دوستان"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=balance_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "stats":
        win_rate = 0
        if user_data['games_played'] > 0:
            win_rate = (user_data['total_wins'] / user_data['games_played']) * 100
        
        stats_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        stats_text += "┃    📊 آمار من    ┃\n"
        stats_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        stats_text += f"💰 موجودی: {user_data['balance']} 🦮\n\n"
        stats_text += "┌─ 🎮 آمار بازی‌ها\n"
        stats_text += "│\n"
        stats_text += f"├─ تعداد: {user_data['games_played']}\n"
        stats_text += f"├─ برد: {user_data['total_wins']} ✅\n"
        stats_text += f"├─ باخت: {user_data['total_losses']} ❌\n"
        stats_text += f"└─ درصد برد: {win_rate:.1f}%\n\n"
        stats_text += f"🎁 دعوت‌های شما: {len(user_data.get('referrals', []))}"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=stats_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "deposit":
        deposit_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        deposit_text += "┃   💎 واریز Dogs   ┃\n"
        deposit_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        deposit_text += f"🔗 کانال ما: {CHANNEL_USERNAME}\n\n"
        deposit_text += "┌─ 📝 مراحل واریز\n"
        deposit_text += "│\n"
        deposit_text += "├─ 1️⃣ در کانال عضو شوید\n"
        deposit_text += "├─ 2️⃣ پیام پین شده را ببینید\n"
        deposit_text += "├─ 3️⃣ داگز را انتقال دهید\n"
        deposit_text += "└─ 4️⃣ منتظر تایید باشید\n\n"
        deposit_text += f"🆔 شناسه شما: {user_id}\n\n"
        deposit_text += "⚡️ پس از تایید، موجودی به حساب شما اضافه می‌شود"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=deposit_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    if data == "withdraw":
        if user_data['balance'] <= 0:
            error_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            error_text += "┃   ⚠️ موجودی صفر   ┃\n"
            error_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            error_text += "موجودی شما برای برداشت کافی نیست!\n\n"
            error_text += "💡 برای افزایش موجودی:\n"
            error_text += "├─ 🎮 بازی کنید\n"
            error_text += "└─ 💎 واریز کنید"
            
            await query.answer("❌ موجودی صفر است!", show_alert=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=error_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        if user_data['games_played'] < MIN_GAMES_FOR_WITHDRAWAL:
            remaining_games = MIN_GAMES_FOR_WITHDRAWAL - user_data['games_played']
            
            error_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            error_text += "┃  ⚠️ شرط برداشت   ┃\n"
            error_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            error_text += f"🎮 حداقل {MIN_GAMES_FOR_WITHDRAWAL} بازی الزامی است\n\n"
            error_text += f"📊 بازی‌های شما: {user_data['games_played']}\n"
            error_text += f"⚠️ باقیمانده: {remaining_games} بازی\n\n"
            error_text += "💡 ابتدا بازی کنید!"
            
            await query.answer(f"❌ {remaining_games} بازی دیگر لازم است!", show_alert=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=error_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        if user_data['balance'] < MIN_WITHDRAWAL:
            error_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            error_text += "┃  ⚠️ حداقل برداشت  ┃\n"
            error_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            error_text += f"💰 موجودی شما: {user_data['balance']} 🦮\n"
            error_text += f"✅ حداقل برداشت: {MIN_WITHDRAWAL} 🦮\n"
            error_text += f"⚠️ کمبود: {MIN_WITHDRAWAL - user_data['balance']} 🦮\n\n"
            error_text += "💡 موجودی خود را افزایش دهید!"
            
            await query.answer(f"❌ حداقل {MIN_WITHDRAWAL} 🦮 لازم است!", show_alert=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=error_text,
                reply_markup=get_back_only_keyboard()
            )
            return
        
        withdraw_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        withdraw_text += "┃  💸 برداشت Dogs  ┃\n"
        withdraw_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        withdraw_text += f"💰 موجودی: {user_data['balance']} 🦮\n"
        withdraw_text += f"✅ حداقل: {MIN_WITHDRAWAL} 🦮\n"
        withdraw_text += f"🎮 بازی‌ها: {user_data['games_played']}\n\n"
        withdraw_text += "┌─ 📝 اطلاعات لازم\n"
        withdraw_text += "│\n"
        withdraw_text += "├─ نام کاربری @\n"
        withdraw_text += "└─ ایدی عددی\n\n"
        withdraw_text += "💬 مثال:\n@username\n123456789"
        
        context.user_data['waiting_for_withdrawal'] = True
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=withdraw_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    if data == "referral":
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        referral_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        referral_text += "┃  🎁 دعوت دوستان  ┃\n"
        referral_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        referral_text += f"🎁 هر دعوت = {REFERRAL_REWARD} 🦮\n\n"
        referral_text += "┌─ 🔗 لینک اختصاصی شما\n"
        referral_text += "│\n"
        referral_text += f"└─ {referral_link}\n\n"
        referral_text += f"👥 دعوت‌های شما: {len(user_data.get('referrals', []))}\n"
        referral_text += f"💰 درآمد کل: {len(user_data.get('referrals', []))*REFERRAL_REWARD} 🦮"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=referral_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if data == "support":
        context.user_data['waiting_for_support'] = True
        
        support_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        support_text += "┃   📞 پشتیبانی    ┃\n"
        support_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        support_text += "💬 پیام خود را برای تیم پشتیبانی ارسال کنید\n\n"
        support_text += "⚡️ پیام شما مستقیماً به ادمین ارسال می‌شود"
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=support_text,
            reply_markup=get_back_only_keyboard()
        )
        return
    
    if data == "admin_panel" and user_id == ADMIN_ID:
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  👨‍💼 پنل مدیریت  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
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
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  👥 آمار کاربران  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += f"📊 کل کاربران: {total_users}\n"
        admin_text += f"🚫 مسدود شده: {blocked_users}\n"
        admin_text += f"🎮 کل بازی‌ها: {total_games}"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_games" and user_id == ADMIN_ID:
        recent_games = games_db[-10:] if len(games_db) > 10 else games_db
        
        games_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        games_text += "┃  🎮 آخرین بازی‌ها  ┃\n"
        games_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        for game in reversed(recent_games):
            result = "✅" if game['won'] else "❌"
            username = game.get('username', 'unknown')
            games_text += f"{result} @{username}\n"
            games_text += f"   {game['game_type']} | {game['bet_amount']} 🦮\n\n"
        
        if not recent_games:
            games_text += "هیچ بازی‌ای ثبت نشده"
        
        await query.edit_message_text(games_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_add_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'add_balance'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  ➕ افزایش موجودی  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر مبلغ\n\n"
        admin_text += "📝 مثال:\n123456789 100"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_reduce_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'reduce_balance'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  ➖ کاهش موجودی  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر مبلغ\n\n"
        admin_text += "📝 مثال:\n123456789 50"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_block" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'block_user'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃   🚫 بلاک کاربر   ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 ایدی کاربر را ارسال کنید:\n\n"
        admin_text += "📝 مثال:\n123456789"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_unblock" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'unblock_user'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  ✅ آنبلاک کاربر  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 ایدی کاربر را ارسال کنید:\n\n"
        admin_text += "📝 مثال:\n123456789"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_withdrawals" and user_id == ADMIN_ID:
        pending_withdrawals = [w for w in withdrawals_db if w.get('status') == 'pending']
        
        withdrawal_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        withdrawal_text += "┃  📋 درخواست‌ها   ┃\n"
        withdrawal_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        if not pending_withdrawals:
            withdrawal_text += "هیچ درخواستی وجود ندارد"
        else:
            for w in pending_withdrawals:
                withdrawal_text += f"👤 {w['username']}\n"
                withdrawal_text += f"🆔 {w['user_id']}\n"
                withdrawal_text += f"💰 {w['amount']} 🦮\n\n"
        
        await query.edit_message_text(withdrawal_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'broadcast'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  📢 ارسال همگانی  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 پیام خود را ارسال کنید\n\n"
        admin_text += "⚡️ به تمام کاربران ارسال می‌شود"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_send_user" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'send_user'
        
        admin_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        admin_text += "┃  💬 ارسال خصوصی  ┃\n"
        admin_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        admin_text += "💬 فرمت ارسال:\n\n"
        admin_text += "ایدی_کاربر پیام\n\n"
        admin_text += "📝 مثال:\n123456789 سلام"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "back_to_main":
        context.user_data.clear()
        
        back_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        back_text += "┃   🏠 منوی اصلی   ┃\n"
        back_text += "┗━━━━━━━━━━━━━━━━━━━┛"
        
        await query.edit_message_text(
            back_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    chat_type = update.message.chat.type
    
    if chat_type in ['group', 'supergroup'] and user_id == ADMIN_ID:
        if update.message.reply_to_message:
            if text.startswith('+') or text.startswith('-'):
                try:
                    amount = int(text)
                    target_user_id = update.message.reply_to_message.from_user.id
                    target_username = update.message.reply_to_message.from_user.username
                    
                    if target_user_id not in users_db:
                        create_user(target_user_id, target_username)
                    
                    if amount > 0:
                        reason = "افزایش توسط ادمین در گروه"
                    else:
                        reason = "کاهش توسط ادمین در گروه"
                    
                    await update_balance(target_user_id, amount, context, reason)
                    
                    new_balance = users_db[target_user_id]['balance']
                    
                    result_text = f"{'✅' if amount > 0 else '⚠️'} موجودی تغییر کرد\n\n"
                    result_text += f"👤 @{target_username or target_user_id}\n"
                    result_text += f"{'➕' if amount > 0 else '➖'} {abs(amount)} 🦮\n"
                    result_text += f"💰 موجودی: {new_balance} 🦮"
                    
                    await update.message.reply_text(result_text)
                    return
                except ValueError:
                    await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: +100 یا -50")
                    return
                except Exception as e:
                    logger.error(f"خطا در تغییر موجودی: {e}")
                    await update.message.reply_text(f"❌ خطا: {str(e)}")
                    return
    
    if context.user_data.get('waiting_for_custom_bet'):
        try:
            bet_amount = int(text.strip())
            
            if bet_amount < MIN_BET:
                error_text = f"❌ مبلغ باید حداقل {MIN_BET} 🦮 باشد!\n\n"
                error_text += "💬 دوباره وارد کنید:"
                
                await update.message.reply_text(
                    error_text,
                    reply_markup=get_back_only_keyboard()
                )
                return
            
            user_data = get_user(user_id)
            if user_data['balance'] < bet_amount:
                error_text = "❌ موجودی کافی نیست!\n\n"
                error_text += f"💰 موجودی شما: {user_data['balance']} 🦮\n"
                error_text += f"💎 مبلغ درخواستی: {bet_amount} 🦮"
                
                await update.message.reply_text(
                    error_text,
                    reply_markup=get_back_only_keyboard()
                )
                return
            
            game_type = context.user_data.get('current_game', 'football')
            context.user_data['waiting_for_custom_bet'] = False
            
            game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
            dice_message = await context.bot.send_dice(
                chat_id=update.message.chat_id,
                emoji=game_emoji
            )
            
            dice_value = dice_message.dice.value
            win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
            
            if win:
                reward = bet_amount * 2
                await update_balance(user_id, reward, context, f"برد در {GAME_NAMES[game_type]}")
                
                result_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
                result_text += "┃   🎉 برنده شدید!   ┃\n"
                result_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
                result_text += f"🎮 {GAME_NAMES[game_type]}\n"
                result_text += f"🎯 نتیجه: {dice_value}\n"
                result_text += f"💰 شرط: {bet_amount} 🦮\n"
                result_text += f"🎁 برد: {reward} 🦮\n"
                
                users_db[user_id]["total_wins"] += 1
                users_db[user_id]["games_played"] += 1
            else:
                await update_balance(user_id, -bet_amount, context)
                
                result_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
                result_text += "┃    😔 باختید!     ┃\n"
                result_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
                result_text += f"🎮 {GAME_NAMES[game_type]}\n"
                result_text += f"🎯 نتیجه: {dice_value}\n"
                result_text += f"💸 باخت: {bet_amount} 🦮\n"
                
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
            result_text += f"\n💰 موجودی: {updated_user['balance']} 🦮"
            
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=result_text,
                reply_markup=get_main_keyboard(user_id == ADMIN_ID)
            )
            return
            
        except ValueError:
            await update.message.reply_text(
                "❌ فقط عدد وارد کنید!\n\n📝 مثال: 25",
                reply_markup=get_back_only_keyboard()
            )
            return
    
    if context.user_data.get('waiting_for_withdrawal'):
        user_data = get_user(user_id)
        
        withdrawal_data = {
            "user_id": user_id,
            "username": update.effective_user.username,
            "amount": user_data['balance'],
            "withdrawal_info": text,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        withdrawals_db.append(withdrawal_data)
        
        try:
            admin_notif = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            admin_notif += "┃  🔔 درخواست جدید  ┃\n"
            admin_notif += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            admin_notif += f"👤 @{update.effective_user.username}\n"
            admin_notif += f"🆔 {user_id}\n"
            admin_notif += f"💰 {user_data['balance']} 🦮\n\n"
            admin_notif += f"📝 اطلاعات:\n{text}"
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notif
            )
        except:
            pass
        
        context.user_data['waiting_for_withdrawal'] = False
        
        success_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
        success_text += "┃   ✅ ثبت شد!    ┃\n"
        success_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
        success_text += "درخواست برداشت شما ثبت شد\n\n"
        success_text += "⏳ بعد از بررسی، Dogs واریز می‌شود"
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )
        return
    
    if context.user_data.get('waiting_for_support'):
        try:
            support_notif = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            support_notif += "┃  📞 پیام جدید   ┃\n"
            support_notif += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            support_notif += f"👤 @{update.effective_user.username}\n"
            support_notif += f"🆔 {user_id}\n\n"
            support_notif += f"💬 پیام:\n{text}"
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=support_notif
            )
            
            context.user_data['waiting_for_support'] = False
            
            success_text = "┏━━━━━━━━━━━━━━━━━━━┓\n"
            success_text += "┃   ✅ ارسال شد!   ┃\n"
            success_text += "┗━━━━━━━━━━━━━━━━━━━┛\n\n"
            success_text += "پیام شما به پشتیبانی ارسال شد\n\n"
            success_text += "⏳ به زودی پاسخ داده می‌شود"
            
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
                
                success_text = f"✅ موجودی افزایش یافت\n\n"
                success_text += f"🆔 {target_user_id}\n"
                success_text += f"➕ {amount} 🦮"
                
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
                
                success_text = f"✅ موجودی کاهش یافت\n\n"
                success_text += f"🆔 {target_user_id}\n"
                success_text += f"➖ {amount} 🦮"
                
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
            
            broadcast_msg = f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            broadcast_msg += f"┃  📢 پیام مدیریت  ┃\n"
            broadcast_msg += f"┗━━━━━━━━━━━━━━━━━━━┛\n\n"
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
            
            result_text = f"✅ ارسال انجام شد\n\n"
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
                
                personal_msg = f"┏━━━━━━━━━━━━━━━━━━━┓\n"
                personal_msg += f"┃  📬 پیام مدیریت  ┃\n"
                personal_msg += f"┗━━━━━━━━━━━━━━━━━━━┛\n\n"
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
