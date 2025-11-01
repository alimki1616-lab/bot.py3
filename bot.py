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
MIN_WINS_FOR_WITHDRAWAL = 5  # 🔧 تغییر از MIN_GAMES به MIN_WINS
MIN_BET = 1
REFERRAL_REWARD = 1
INITIAL_BALANCE = 2

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN تنظیم نشده! لطفاً در .env یا Railway تنظیم کنید.")

users_db = {}
games_db = []
withdrawals_db = []

# آمار کل سیستم
total_stars_earned = 0
total_stars_lost = 0

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# چند زبانه - Multilingual
LANGUAGES = {
    'fa': {
        'language_name': '🇮🇷 فارسی',
        'select_language': 'لطفاً زبان خود را انتخاب کنید:',
        'language_changed': '✅ زبان با موفقیت تغییر کرد!',
        'membership_required': '🔐 عضویت لازم',
        'must_join': '⚠️ برای استفاده از ربات\nابتدا باید در کانال عضو شوید',
        'our_channel': '📢 کانال ما:',
        'after_join': "✨ بعد از عضویت، دکمه\n'🔄 بررسی عضویت' را بزنید",
        'join_channel': '✅ عضویت در کانال',
        'check_membership': '🔄 بررسی عضویت',
        'membership_confirmed': '✅ عضویت شما تأیید شد!\n\n🎉 از دستور /start استفاده کنید.',
        'not_joined_yet': '❌ هنوز در کانال عضو نشده‌اید!',
        'welcome_title': '🎮 به دنیای هیجان خوش آمدید',
        'hello': '👋 سلام',
        'your_wallet': '💎 موجودی شما:',
        'exciting_games': '🎯 بازی‌های هیجان‌انگیز:',
        'ready_to_win': '🔥 آماده‌اید برای برد بزرگ؟',
        'football': '⚽ فوتبال',
        'basketball': '🏀 بسکتبال',
        'dart': '🎯 دارت',
        'bowling': '🎳 بولینگ',
        'slot': '🎰 اسلات',
        'dice': '🎲 تاس',
        'my_balance': '💰 موجودی من',
        'my_stats': '📊 آمار من',
        'deposit': '💎 واریز',
        'withdraw': '💸 برداشت',
        'invite_friends': '🎁 دعوت دوستان',
        'support': '📞 پشتیبانی',
        'settings': '⚙️ تنظیمات',
        'football_guide': '⚽ برای برد باید توپ وارد دروازه شود',
        'basketball_guide': '🏀 برای برد باید توپ داخل سبد برود',
        'dart_guide': '🎯 برای برد باید دارت به مرکز هدف بخورد',
        'bowling_guide': '🎳 برای برد باید تمام پین‌ها بیفتند',
        'slot_guide': '🎰 برای برد باید 3 نماد یکسان بیاید',
        'dice_guide': '🎲 برای برد باید عدد 6 بیاید',
        'how_much_bet': '💰 چقدر می‌خوای شرط ببندی؟',
        'wallet': '📊 کیف پول:',
        'min_bet': '🎯 حداقل شرط:',
        'win_double': '🔥 برد = ضربدر 2 شرط شما!',
        'custom_amount': '💰 مبلغ دلخواه',
        'your_balance': '📊 موجودی شما:',
        'enter_amount': '💬 مبلغ را وارد کنید:',
        'back': '🔙 بازگشت',
        'insufficient_balance': '❌ موجودی کافی نیست!',
        'game_in_progress': '🎲 بازی در حال انجامه...',
        'your_bet': '💰 شرط شما:',
        'good_luck': '🤞 خدا خدا کن برنده شی!',
        'you_won': '🎉 برنده شدی!',
        'game': '🎮 بازی:',
        'result': '🎯 نتیجه:',
        'bet': '💰 شرط:',
        'prize': '🎁 جایزه:',
        'you_lost': '😔 این دفعه نشد!',
        'lost': '💸 از دست رفت:',
        'dont_give_up': '💪 نا امید نشو!\nدفعه بعد می‌بری! 🔥',
        'new_balance': '💰 موجودی جدید:',
        'your_wallet_title': '💎 کیف پول شما',
        'current_balance': '✨ موجودی فعلی شما:',
        'ways_to_increase': '🚀 راه‌های افزایش موجودی:',
        'win_games': '🎮 برد در بازی‌ها',
        'deposit_stars': '💎 واریز Stars',
        'invite_earn': '🎁 دعوت دوستان',
        'start_now': '💪 همین الان شروع کن!',
        'your_stats_title': '📊 آمار شما',
        'games_stats': '🎮 آمار بازی‌ها:',
        'total_games': '🎯 کل بازی‌ها:',
        'wins': '✅ برد:',
        'losses': '❌ باخت:',
        'games': 'بازی',
        'win_rate': '📈 نرخ برد:',
        'successful_invites': '🎁 دعوت‌های موفق:',
        'people': 'نفر',
        'invite_income': '💎 درآمد دعوت:',
        'keep_going': '🔥 به راه خود ادامه بده!',
        'deposit_instruction': 'برای واریز کردن ⭐ روی دکمه زیر کلیک کنید :',
        'insufficient_balance_title': '⚠️ موجودی ناکافی!',
        'no_balance': '😕 متاسفانه موجودی کافی نیست!',
        'solutions': '💡 راه‌حل‌ها:',
        'play_and_win': '🎮 بازی و برد',
        'charge_now': '🚀 همین الان شارژ کن!',
        'balance_zero': '❌ موجودی صفر است!',
        'withdrawal_condition': '🎮 شرط برای برداشت!',
        'min_wins_required': '⚠️ برای برداشت باید حداقل',  # 🔧 جدید
        'wins_complete': 'برد داشته باشی!',  # 🔧 جدید
        'your_wins': '📊 برد های تو:',  # 🔧 جدید
        'remaining': '⚡️ باقیمانده:',
        'lets_play': '🎯 بریم بازی کنیم! 🔥',
        'more_wins_needed': 'برد دیگر لازم است!',  # 🔧 جدید
        'withdraw_prizes': '💸 برداشت جوایز',
        'completed_games': '🎮 بازی‌های انجام شده:',
        'amazing_prizes': '🎁 جوایز شگفت‌انگیز:',
        'teddy': '🧸 تدی',
        'flower': '🌹 گل',
        'rocket': '🚀 موشک',
        'only': 'فقط',
        'choose_prize': '✨ جایزه رو انتخاب کن!',
        'invalid_option': '❌ گزینه نامعتبر!',
        'not_enough': '❌ موجودی کافی نیست!',
        'shortage': 'کم دارید',
        'send_id': '📝 ارسال آیدی',
        'option': '🎁 گزینه:',
        'amount': '💰 مبلغ:',
        'send_your_id': '💬 لطفاً آیدی خود را برای\nواریز ارسال کنید:',
        'example': '📝 مثال:',
        'or': 'یا',
        'referral_title': '🎁 دعوت دوستان = درآمد!',
        'per_friend': '✨ هر دوست =',
        'to_your_wallet': 'به کیف پول شما!',
        'your_link': '🔗 لینک اختصاصی شما:',
        'your_stats': '📊 آمار شما:',
        'total_income': '💰 کل درآمد:',
        'invite_more': '🚀 بیشتر دعوت کن، بیشتر ببر!',
        'support_247': '📞 پشتیبانی 24/7',
        'have_question': '💬 سوال یا مشکلی داری?\nتیم ما آماده کمکه! 🤝',
        'write_message': '✍️ پیامت رو بنویس و ارسال کن',
        'direct_to_admin': '⚡️ مستقیم به ادمین می‌رسه!\n⏱ در اسرع وقت پاسخ می‌دیم',
        'back_to_menu': '🔙 بازگشت به منو',
        'main_menu': '🏠 منوی اصلی',
        'admin_panel': '👨‍💼 پنل مدیریت',
        'min_amount': '❌ مبلغ باید حداقل',
        'be': 'باشد!',
        'enter_again': '💬 دوباره وارد کنید:',
        'requested': '💎 درخواستی:',
        'only_number': '❌ فقط عدد وارد کنید!',
        'request_submitted': '✅ درخواست برداشت با موفقیت ثبت شد!',
        'deducted': 'از موجودی کسر شد',
        'team_reviewing': '⏱ تیم ما داره بررسی می‌کنه\n🎁 به زودی هدیه ارسال می‌شه!',
        'thanks': '💌 ممنون از صبرت!',
        'sent': '✅ ارسال شد!',
        'message_sent_support': 'پیام شما به پشتیبانی ارسال شد',
        'will_reply_soon': '⏳ به زودی پاسخ داده می‌شود',
        'send_error': '❌ خطا در ارسال. بعداً تلاش کنید',
        'change_language': '🌐 تغییر زبان',
    },
    'en': {
        'language_name': '🇬🇧 English',
        'select_language': 'Please select your language:',
        'language_changed': '✅ Language changed successfully!',
        'membership_required': '🔐 Membership Required',
        'must_join': '⚠️ To use the bot\nYou must first join the channel',
        'our_channel': '📢 Our channel:',
        'after_join': "✨ After joining, click\n'🔄 Check Membership' button",
        'join_channel': '✅ Join Channel',
        'check_membership': '🔄 Check Membership',
        'membership_confirmed': '✅ Your membership is confirmed!\n\n🎉 Use /start command.',
        'not_joined_yet': '❌ You have not joined the channel yet!',
        'welcome_title': '🎮 Welcome to the World of Excitement',
        'hello': '👋 Hello',
        'your_wallet': '💎 Your balance:',
        'exciting_games': '🎯 Exciting Games:',
        'ready_to_win': '🔥 Ready for a big win?',
        'football': '⚽ Football',
        'basketball': '🏀 Basketball',
        'dart': '🎯 Dart',
        'bowling': '🎳 Bowling',
        'slot': '🎰 Slot',
        'dice': '🎲 Dice',
        'my_balance': '💰 My Balance',
        'my_stats': '📊 My Stats',
        'deposit': '💎 Deposit',
        'withdraw': '💸 Withdraw',
        'invite_friends': '🎁 Invite Friends',
        'support': '📞 Support',
        'settings': '⚙️ Settings',
        'football_guide': '⚽ To win, the ball must go into the goal',
        'basketball_guide': '🏀 To win, the ball must go into the basket',
        'dart_guide': '🎯 To win, the dart must hit the center',
        'bowling_guide': '🎳 To win, all pins must fall',
        'slot_guide': '🎰 To win, 3 identical symbols must appear',
        'dice_guide': '🎲 To win, you must roll a 6',
        'how_much_bet': '💰 How much do you want to bet?',
        'wallet': '📊 Wallet:',
        'min_bet': '🎯 Minimum bet:',
        'win_double': '🔥 Win = 2x your bet!',
        'custom_amount': '💰 Custom Amount',
        'your_balance': '📊 Your balance:',
        'enter_amount': '💬 Enter amount:',
        'back': '🔙 Back',
        'insufficient_balance': '❌ Insufficient balance!',
        'game_in_progress': '🎲 Game in progress...',
        'your_bet': '💰 Your bet:',
        'good_luck': '🤞 Good luck!',
        'you_won': '🎉 You won!',
        'game': '🎮 Game:',
        'result': '🎯 Result:',
        'bet': '💰 Bet:',
        'prize': '🎁 Prize:',
        'you_lost': '😔 Not this time!',
        'lost': '💸 Lost:',
        'dont_give_up': "💪 Don't give up!\nYou'll win next time! 🔥",
        'new_balance': '💰 New balance:',
        'your_wallet_title': '💎 Your Wallet',
        'current_balance': '✨ Your current balance:',
        'ways_to_increase': '🚀 Ways to increase balance:',
        'win_games': '🎮 Win games',
        'deposit_stars': '💎 Deposit Stars',
        'invite_earn': '🎁 Invite friends',
        'start_now': '💪 Start now!',
        'your_stats_title': '📊 Your Stats',
        'games_stats': '🎮 Games Statistics:',
        'total_games': '🎯 Total games:',
        'wins': '✅ Wins:',
        'losses': '❌ Losses:',
        'games': 'games',
        'win_rate': '📈 Win rate:',
        'successful_invites': '🎁 Successful invites:',
        'people': 'people',
        'invite_income': '💎 Invite income:',
        'keep_going': '🔥 Keep going!',
        'deposit_instruction': 'To deposit ⭐ click the button below:',
        'insufficient_balance_title': '⚠️ Insufficient Balance!',
        'no_balance': '😕 Unfortunately insufficient balance!',
        'solutions': '💡 Solutions:',
        'play_and_win': '🎮 Play and win',
        'charge_now': '🚀 Charge now!',
        'balance_zero': '❌ Balance is zero!',
        'withdrawal_condition': '🎮 Withdrawal Condition!',
        'min_wins_required': '⚠️ You must have at least',
        'wins_complete': 'wins to withdraw!',
        'your_wins': '📊 Your wins:',
        'remaining': '⚡️ Remaining:',
        'lets_play': "🎯 Let's play! 🔥",
        'more_wins_needed': 'more wins needed!',
        'withdraw_prizes': '💸 Withdraw Prizes',
        'completed_games': '🎮 Completed games:',
        'amazing_prizes': '🎁 Amazing prizes:',
        'teddy': '🧸 Teddy',
        'flower': '🌹 Flower',
        'rocket': '🚀 Rocket',
        'only': 'only',
        'choose_prize': '✨ Choose your prize!',
        'invalid_option': '❌ Invalid option!',
        'not_enough': '❌ Not enough balance!',
        'shortage': 'short',
        'send_id': '📝 Send ID',
        'option': '🎁 Option:',
        'amount': '💰 Amount:',
        'send_your_id': '💬 Please send your ID\nfor deposit:',
        'example': '📝 Example:',
        'or': 'or',
        'referral_title': '🎁 Invite Friends = Earn!',
        'per_friend': '✨ Per friend =',
        'to_your_wallet': 'to your wallet!',
        'your_link': '🔗 Your exclusive link:',
        'your_stats': '📊 Your stats:',
        'total_income': '💰 Total income:',
        'invite_more': '🚀 Invite more, earn more!',
        'support_247': '📞 24/7 Support',
        'have_question': '💬 Have a question or problem?\nOur team is ready to help! 🤝',
        'write_message': '✍️ Write and send your message',
        'direct_to_admin': '⚡️ Goes directly to admin!\n⏱ We will respond ASAP',
        'back_to_menu': '🔙 Back to Menu',
        'main_menu': '🏠 Main Menu',
        'admin_panel': '👨‍💼 Admin Panel',
        'min_amount': '❌ Amount must be at least',
        'be': '!',
        'enter_again': '💬 Enter again:',
        'requested': '💎 Requested:',
        'only_number': '❌ Enter numbers only!',
        'request_submitted': '✅ Withdrawal request submitted successfully!',
        'deducted': 'deducted from balance',
        'team_reviewing': '⏱ Our team is reviewing\n🎁 Gift will be sent soon!',
        'thanks': '💌 Thanks for your patience!',
        'sent': '✅ Sent!',
        'message_sent_support': 'Your message sent to support',
        'will_reply_soon': '⏳ Will reply soon',
        'send_error': '❌ Send error. Try later',
        'change_language': '🌐 Change Language',
    },
    'ru': {
        'language_name': '🇷🇺 Русский',
        'select_language': 'Пожалуйста, выберите ваш язык:',
        'language_changed': '✅ Язык успешно изменен!',
        'membership_required': '🔐 Требуется членство',
        'must_join': '⚠️ Чтобы использовать бота\nСначала необходимо вступить в канал',
        'our_channel': '📢 Наш канал:',
        'after_join': "✨ После вступления нажмите\nкнопку '🔄 Проверить членство'",
        'join_channel': '✅ Вступить в канал',
        'check_membership': '🔄 Проверить членство',
        'membership_confirmed': '✅ Ваше членство подтверждено!\n\n🎉 Используйте команду /start.',
        'not_joined_yet': '❌ Вы еще не вступили в канал!',
        'welcome_title': '🎮 Добро пожаловать в мир азарта',
        'hello': '👋 Привет',
        'your_wallet': '💎 Ваш баланс:',
        'exciting_games': '🎯 Увлекательные игры:',
        'ready_to_win': '🔥 Готовы к большому выигрышу?',
        'football': '⚽ Футбол',
        'basketball': '🏀 Баскетбол',
        'dart': '🎯 Дартс',
        'bowling': '🎳 Боулинг',
        'slot': '🎰 Слот',
        'dice': '🎲 Кости',
        'my_balance': '💰 Мой баланс',
        'my_stats': '📊 Моя статистика',
        'deposit': '💎 Депозит',
        'withdraw': '💸 Вывод',
        'invite_friends': '🎁 Пригласить друзей',
        'support': '📞 Поддержка',
        'settings': '⚙️ Настройки',
        'football_guide': '⚽ Чтобы выиграть, мяч должен попасть в ворота',
        'basketball_guide': '🏀 Чтобы выиграть, мяч должен попасть в корзину',
        'dart_guide': '🎯 Чтобы выиграть, дротик должен попасть в центр',
        'bowling_guide': '🎳 Чтобы выиграть, все кегли должны упасть',
        'slot_guide': '🎰 Чтобы выиграть, должны появиться 3 одинаковых символа',
        'dice_guide': '🎲 Чтобы выиграть, нужно выбросить 6',
        'how_much_bet': '💰 Сколько хотите поставить?',
        'wallet': '📊 Кошелек:',
        'min_bet': '🎯 Минимальная ставка:',
        'win_double': '🔥 Выигрыш = 2x вашей ставки!',
        'custom_amount': '💰 Своя сумма',
        'your_balance': '📊 Ваш баланс:',
        'enter_amount': '💬 Введите сумму:',
        'back': '🔙 Назад',
        'insufficient_balance': '❌ Недостаточно средств!',
        'game_in_progress': '🎲 Игра в процессе...',
        'your_bet': '💰 Ваша ставка:',
        'good_luck': '🤞 Удачи!',
        'you_won': '🎉 Вы выиграли!',
        'game': '🎮 Игра:',
        'result': '🎯 Результат:',
        'bet': '💰 Ставка:',
        'prize': '🎁 Приз:',
        'you_lost': '😔 Не в этот раз!',
        'lost': '💸 Проиграно:',
        'dont_give_up': '💪 Не сдавайтесь!\nВы выиграете в следующий раз! 🔥',
        'new_balance': '💰 Новый баланс:',
        'your_wallet_title': '💎 Ваш кошелек',
        'current_balance': '✨ Ваш текущий баланс:',
        'ways_to_increase': '🚀 Способы увеличить баланс:',
        'win_games': '🎮 Выигрывать в играх',
        'deposit_stars': '💎 Пополнить Stars',
        'invite_earn': '🎁 Пригласить друзей',
        'start_now': '💪 Начать сейчас!',
        'your_stats_title': '📊 Ваша статистика',
        'games_stats': '🎮 Статистика игр:',
        'total_games': '🎯 Всего игр:',
        'wins': '✅ Побед:',
        'losses': '❌ Поражений:',
        'games': 'игр',
        'win_rate': '📈 Процент побед:',
        'successful_invites': '🎁 Успешных приглашений:',
        'people': 'человек',
        'invite_income': '💎 Доход с приглашений:',
        'keep_going': '🔥 Продолжайте!',
        'deposit_instruction': 'Чтобы пополнить ⭐ нажмите кнопку ниже:',
        'insufficient_balance_title': '⚠️ Недостаточно средств!',
        'no_balance': '😕 К сожалению недостаточно средств!',
        'solutions': '💡 Решения:',
        'play_and_win': '🎮 Играть и выигрывать',
        'charge_now': '🚀 Пополнить сейчас!',
        'balance_zero': '❌ Баланс нулевой!',
        'withdrawal_condition': '🎮 Условие для вывода!',
        'min_wins_required': '⚠️ Вы должны иметь минимум',
        'wins_complete': 'побед для вывода!',
        'your_wins': '📊 Ваши победы:',
        'remaining': '⚡️ Осталось:',
        'lets_play': '🎯 Давайте играть! 🔥',
        'more_wins_needed': 'еще побед нужно!',
        'withdraw_prizes': '💸 Вывести призы',
        'completed_games': '🎮 Завершенные игры:',
        'amazing_prizes': '🎁 Удивительные призы:',
        'teddy': '🧸 Мишка',
        'flower': '🌹 Цветок',
        'rocket': '🚀 Ракета',
        'only': 'только',
        'choose_prize': '✨ Выберите свой приз!',
        'invalid_option': '❌ Неверный вариант!',
        'not_enough': '❌ Недостаточно средств!',
        'shortage': 'не хватает',
        'send_id': '📝 Отправить ID',
        'option': '🎁 Вариант:',
        'amount': '💰 Сумма:',
        'send_your_id': '💬 Пожалуйста, отправьте ваш ID\nдля пополнения:',
        'example': '📝 Пример:',
        'or': 'или',
        'referral_title': '🎁 Пригласить друзей = Заработать!',
        'per_friend': '✨ За друга =',
        'to_your_wallet': 'на ваш кошелек!',
        'your_link': '🔗 Ваша эксклюзивная ссылка:',
        'your_stats': '📊 Ваша статистика:',
        'total_income': '💰 Общий доход:',
        'invite_more': '🚀 Приглашайте больше, зарабатывайте больше!',
        'support_247': '📞 Поддержка 24/7',
        'have_question': '💬 Есть вопрос или проблема?\nНаша команда готова помочь! 🤝',
        'write_message': '✍️ Напишите и отправьте сообщение',
        'direct_to_admin': '⚡️ Идет напрямую администратору!\n⏱ Ответим как можно скорее',
        'back_to_menu': '🔙 Назад в меню',
        'main_menu': '🏠 Главное меню',
        'admin_panel': '👨‍💼 Панель администратора',
        'min_amount': '❌ Сумма должна быть минимум',
        'be': '!',
        'enter_again': '💬 Введите снова:',
        'requested': '💎 Запрошено:',
        'only_number': '❌ Только числа!',
        'request_submitted': '✅ Запрос на вывод успешно отправлен!',
        'deducted': 'списано с баланса',
        'team_reviewing': '⏱ Наша команда проверяет\n🎁 Подарок будет отправлен скоро!',
        'thanks': '💌 Спасибо за терпение!',
        'sent': '✅ Отправлено!',
        'message_sent_support': 'Ваше сообщение отправлено в поддержку',
        'will_reply_soon': '⏳ Скоро ответим',
        'send_error': '❌ Ошибка отправки. Попробуйте позже',
        'change_language': '🌐 Изменить язык',
    }
}

GAME_EMOJI_MAP = {
    "football": DiceEmoji.FOOTBALL,
    "basketball": DiceEmoji.BASKETBALL,
    "dart": DiceEmoji.DARTS,
    "bowling": DiceEmoji.BOWLING,
    "slot": DiceEmoji.SLOT_MACHINE,
    "dice": DiceEmoji.DICE
}

WINNING_CONDITIONS = {
    "football": [3, 4, 5],
    "basketball": [4, 5],
    "dart": [6],
    "bowling": [6],
    "slot": [1, 22, 43, 64],
    "dice": [6]
}

WITHDRAWAL_OPTIONS = {
    "teddy": {"amount": 15},
    "flower": {"amount": 25},
    "rocket": {"amount": 50}
}

def get_text(user_id: int, key: str) -> str:
    """دریافت متن به زبان کاربر"""
    user_data = users_db.get(user_id)
    if user_data:
        lang = user_data.get('language', 'fa')
    else:
        lang = 'fa'
    return LANGUAGES.get(lang, LANGUAGES['fa']).get(key, key)

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
        "language": "fa",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat()
    }
    users_db[user_id] = user_data
    
    # 🔧 اصلاح: افزودن referral به لیست و ارسال اعلان
    if referred_by and referred_by in users_db:
        users_db[referred_by]["balance"] += REFERRAL_REWARD
        users_db[referred_by]["referrals"].append(user_id)
        logger.info(f"✅ Referral added: {user_id} referred by {referred_by}")
    
    return users_db[user_id]

async def update_balance(user_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE, reason: str = None, send_notification: bool = True):
    global total_stars_earned, total_stars_lost
    
    if user_id in users_db:
        old_balance = users_db[user_id]["balance"]
        users_db[user_id]["balance"] += amount
        new_balance = users_db[user_id]["balance"]
        
        if amount > 0:
            total_stars_earned += amount
        else:
            total_stars_lost += abs(amount)
        
        if amount > 0 and send_notification:
            notification_text = "💎 " + get_text(user_id, 'deposit') + "\n\n"
            notification_text += f"📊 {old_balance} ⭐\n"
            notification_text += f"✨ +{amount} ⭐\n"
            notification_text += f"💰 {new_balance} ⭐\n"
            if reason:
                notification_text += f"\n💬 {reason}"
            
            try:
                await context.bot.send_message(chat_id=user_id, text=notification_text)
            except Exception as e:
                logger.error(f"Error sending notification to {user_id}: {e}")

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton(LANGUAGES['fa']['language_name'], callback_data="lang_fa")],
        [InlineKeyboardButton(LANGUAGES['en']['language_name'], callback_data="lang_en")],
        [InlineKeyboardButton(LANGUAGES['ru']['language_name'], callback_data="lang_ru")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard(user_id: int, is_admin=False):
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'football'), callback_data="game_football"),
         InlineKeyboardButton(get_text(user_id, 'basketball'), callback_data="game_basketball")],
        [InlineKeyboardButton(get_text(user_id, 'dart'), callback_data="game_dart"),
         InlineKeyboardButton(get_text(user_id, 'bowling'), callback_data="game_bowling")],
        [InlineKeyboardButton(get_text(user_id, 'slot'), callback_data="game_slot"),
         InlineKeyboardButton(get_text(user_id, 'dice'), callback_data="game_dice")],
        [InlineKeyboardButton(get_text(user_id, 'my_balance'), callback_data="balance"),
         InlineKeyboardButton(get_text(user_id, 'my_stats'), callback_data="stats")],
        [InlineKeyboardButton(get_text(user_id, 'deposit'), callback_data="deposit"),
         InlineKeyboardButton(get_text(user_id, 'withdraw'), callback_data="withdraw")],
        [InlineKeyboardButton(get_text(user_id, 'invite_friends'), callback_data="referral")],
        [InlineKeyboardButton(get_text(user_id, 'support'), callback_data="support"),
         InlineKeyboardButton(get_text(user_id, 'change_language'), callback_data="change_language")]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton(get_text(user_id, 'admin_panel'), callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 آمار کاربران", callback_data="admin_users"),
         InlineKeyboardButton("🎮 بازی‌ها", callback_data="admin_games")],
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user")],  # 🔧 جدید
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

def get_bet_amount_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("1 ⭐", callback_data="bet_1"),
         InlineKeyboardButton("5 ⭐", callback_data="bet_5"),
         InlineKeyboardButton("10 ⭐", callback_data="bet_10")],
        [InlineKeyboardButton(get_text(user_id, 'custom_amount'), callback_data="bet_custom")],
        [InlineKeyboardButton(get_text(user_id, 'back'), callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_withdrawal_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton(f"{get_text(user_id, 'teddy')} - 15 ⭐", callback_data="withdraw_teddy")],
        [InlineKeyboardButton(f"{get_text(user_id, 'flower')} - 25 ⭐", callback_data="withdraw_flower")],
        [InlineKeyboardButton(f"{get_text(user_id, 'rocket')} - 50 ⭐", callback_data="withdraw_rocket")],
        [InlineKeyboardButton(get_text(user_id, 'back'), callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_only_keyboard(user_id: int):
    keyboard = [[InlineKeyboardButton(get_text(user_id, 'back_to_menu'), callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    # 🔧 اصلاح: بهبود شناسایی referred_by
    referred_by = None
    if context.args:
        logger.info(f"Start command args: {context.args}")
        if len(context.args) > 0 and context.args[0].startswith('ref'):
            try:
                referred_by = int(context.args[0][3:])
                logger.info(f"✅ Referral detected: User {user_id} referred by {referred_by}")
            except ValueError as e:
                logger.error(f"Error parsing referral code: {e}")
    
    is_member = await check_channel_membership(user_id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
        keyboard.append([InlineKeyboardButton("🔄 Check Membership", callback_data="check_membership")])
        
        membership_text = "🔐 Membership Required\n\n"
        membership_text += "⚠️ To use the bot\nYou must first join the channel\n\n"
        membership_text += f"📢 Our channel: {CHANNEL_USERNAME}\n\n"
        membership_text += "✨ After joining, click\n'🔄 Check Membership' button"
        
        await update.message.reply_text(membership_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text(
            "🌐 Please select your language:\n"
            "🌐 لطفاً زبان خود را انتخاب کنید:\n"
            "🌐 Пожалуйста, выберите ваш язык:",
            reply_markup=get_language_keyboard()
        )
        context.user_data['new_user'] = True
        context.user_data['username'] = username
        context.user_data['referred_by'] = referred_by
        logger.info(f"New user setup: {user_id}, referred_by: {referred_by}")
        return
    
    welcome_text = f"🎮 {get_text(user_id, 'hello')} {user.first_name}!\n\n"
    welcome_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
    welcome_text += f"🎯 {get_text(user_id, 'ready_to_win')}"
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_stars_earned, total_stars_lost
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("lang_"):
        lang_code = data.split("_")[1]
        
        if context.user_data.get('new_user'):
            username = context.user_data.get('username')
            referred_by = context.user_data.get('referred_by')
            
            logger.info(f"Creating new user: {user_id}, username: {username}, referred_by: {referred_by}")
            
            create_user(user_id, username, referred_by)
            users_db[user_id]['language'] = lang_code
            
            # 🔧 اصلاح: ارسال اعلان بهبود یافته به referrer
            if referred_by and referred_by in users_db:
                try:
                    referrer_username = f"@{username}" if username else f"کاربر {user_id}"
                    referrer_lang = users_db[referred_by].get('language', 'fa')
                    
                    notif_text = "🎉 کاربر جدید با لینک شما عضو شد!\n\n"
                    notif_text += f"👤 {referrer_username}\n"
                    notif_text += f"💰 +{REFERRAL_REWARD} ⭐ به کیف پول شما اضافه شد\n\n"
                    notif_text += f"💎 موجودی جدید: {users_db[referred_by]['balance']} ⭐"
                    
                    await context.bot.send_message(chat_id=referred_by, text=notif_text)
                    logger.info(f"✅ Referral notification sent to {referred_by}")
                except Exception as e:
                    logger.error(f"❌ Error sending referral notification to {referred_by}: {e}")
            
            context.user_data.clear()
            
            user_data = users_db[user_id]
            welcome_text = f"🎮 {get_text(user_id, 'hello')} {query.from_user.first_name}!\n\n"
            welcome_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
            welcome_text += f"🎯 {get_text(user_id, 'ready_to_win')}"
            
            await query.edit_message_text(welcome_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        else:
            users_db[user_id]['language'] = lang_code
            
            user_data = get_user(user_id)
            back_text = f"🎮 {get_text(user_id, 'hello')} {query.from_user.first_name}!\n\n"
            back_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
            back_text += f"🎯 {get_text(user_id, 'ready_to_win')}"
            
            await query.edit_message_text(back_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    user_data = get_user(user_id)
    if user_data and user_data.get('is_blocked', False) and user_id != ADMIN_ID:
        await query.edit_message_text("🚫 You are blocked from using the bot.")
        return
    
    if data == "change_language":
        await query.edit_message_text(
            get_text(user_id, 'select_language'),
            reply_markup=get_language_keyboard()
        )
        return
    
    if data == "check_membership":
        is_member = await check_channel_membership(user_id, context)
        if is_member:
            user_data = get_user(user_id)
            if not user_data:
                create_user(user_id, query.from_user.username)
            await query.edit_message_text(get_text(user_id, 'membership_confirmed'))
        else:
            await query.answer(get_text(user_id, 'not_joined_yet'), show_alert=True)
        return
    
    if data.startswith("game_"):
        game_type = data.split("_")[1]
        context.user_data['current_game'] = game_type
        
        game_text = f"🎮 {get_text(user_id, game_type)}\n\n"
        game_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
        game_text += f"{get_text(user_id, 'how_much_bet')}"
        
        await query.edit_message_text(game_text, reply_markup=get_bet_amount_keyboard(user_id))
        return
    
    if data.startswith("bet_"):
        if data == "bet_custom":
            context.user_data['waiting_for_custom_bet'] = True
            context.user_data['game_message_id'] = query.message.message_id
            
            custom_text = f"{get_text(user_id, 'custom_amount')}\n\n"
            custom_text += f"{get_text(user_id, 'your_balance')} {user_data['balance']} ⭐\n"
            custom_text += f"⚠️ {get_text(user_id, 'min_bet')} {MIN_BET} ⭐\n\n"
            custom_text += get_text(user_id, 'enter_amount')
            
            await query.edit_message_text(custom_text, reply_markup=get_back_only_keyboard(user_id))
            return
        
        bet_amount = int(data.split("_")[1])
        
        if user_data['balance'] < bet_amount:
            await query.answer(get_text(user_id, 'insufficient_balance'), show_alert=True)
            return
        
        game_type = context.user_data.get('current_game', 'football')
        
        loading_text = f"⏳ {get_text(user_id, game_type)}\n\n"
        loading_text += f"{get_text(user_id, 'game_in_progress')}\n\n"
        loading_text += f"{get_text(user_id, 'your_bet')} {bet_amount} ⭐\n\n"
        loading_text += get_text(user_id, 'good_luck')
        
        await query.edit_message_text(loading_text)
        
        game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
        dice_message = await context.bot.send_dice(chat_id=query.message.chat_id, emoji=game_emoji)
        
        await asyncio.sleep(4)
        
        dice_value = dice_message.dice.value
        win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
        
        await update_balance(user_id, -bet_amount, context, send_notification=False)
        
        if win:
            reward = bet_amount * 2
            await update_balance(user_id, reward, context, f"{get_text(user_id, 'game')}: {get_text(user_id, game_type)}", send_notification=False)
            
            result_text = f"{get_text(user_id, 'you_won')}\n\n"
            result_text += f"{get_text(user_id, 'game')} {get_text(user_id, game_type)}\n"
            result_text += f"{get_text(user_id, 'result')} {dice_value}\n\n"
            result_text += f"{get_text(user_id, 'bet')} {bet_amount} ⭐\n"
            result_text += f"{get_text(user_id, 'prize')} {reward} ⭐\n"
            
            users_db[user_id]["total_wins"] += 1
            users_db[user_id]["games_played"] += 1
        else:
            result_text = f"{get_text(user_id, 'you_lost')}\n\n"
            result_text += f"{get_text(user_id, 'game')} {get_text(user_id, game_type)}\n"
            result_text += f"{get_text(user_id, 'result')} {dice_value}\n\n"
            result_text += f"{get_text(user_id, 'lost')} {bet_amount} ⭐\n\n"
            result_text += get_text(user_id, 'dont_give_up')
            
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
        result_text += f"\n{get_text(user_id, 'new_balance')} {updated_user['balance']} ⭐"
        
        await query.edit_message_text(result_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if data == "balance":
        balance_text = f"💰 {get_text(user_id, 'your_wallet_title')}\n\n"
        balance_text += f"✨ {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
        balance_text += f"🚀 {get_text(user_id, 'ways_to_increase')}\n"
        balance_text += f"• {get_text(user_id, 'win_games')}\n"
        balance_text += f"• {get_text(user_id, 'deposit_stars')}\n"
        balance_text += f"• {get_text(user_id, 'invite_earn')}"
        
        await query.edit_message_text(balance_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if data == "stats":
        win_rate = 0
        if user_data['games_played'] > 0:
            win_rate = (user_data['total_wins'] / user_data['games_played']) * 100
        
        stats_text = f"📊 {get_text(user_id, 'your_stats_title')}\n\n"
        stats_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
        stats_text += f"🎮 {get_text(user_id, 'games_stats')}\n"
        stats_text += f"• {get_text(user_id, 'total_games')} {user_data['games_played']}\n"
        stats_text += f"• {get_text(user_id, 'wins')} {user_data['total_wins']}\n"
        stats_text += f"• {get_text(user_id, 'losses')} {user_data['total_losses']}\n"
        stats_text += f"• {get_text(user_id, 'win_rate')} {win_rate:.1f}%\n\n"
        stats_text += f"🎁 {get_text(user_id, 'successful_invites')} {len(user_data.get('referrals', []))}\n"
        stats_text += f"💎 {get_text(user_id, 'invite_income')} {len(user_data.get('referrals', []))*REFERRAL_REWARD} ⭐"
        
        await query.edit_message_text(stats_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if data == "deposit":
        deposit_text = get_text(user_id, 'deposit_instruction')
        
        keyboard = [
            [InlineKeyboardButton(f"{get_text(user_id, 'deposit')}", url=DEPOSIT_POST_LINK)],
            [InlineKeyboardButton(get_text(user_id, 'back'), callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(deposit_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # 🔧 اصلاح: شرط برداشت بر اساس تعداد برد
    if data == "withdraw":
        if user_data['balance'] <= 0:
            error_text = f"⚠️ {get_text(user_id, 'insufficient_balance_title')}\n\n"
            error_text += f"😕 {get_text(user_id, 'no_balance')}\n\n"
            error_text += f"💡 {get_text(user_id, 'solutions')}\n"
            error_text += f"• {get_text(user_id, 'deposit_stars')}\n"
            error_text += f"• {get_text(user_id, 'play_and_win')}\n"
            error_text += f"• {get_text(user_id, 'invite_earn')}"
            
            await query.answer(get_text(user_id, 'balance_zero'), show_alert=True)
            await query.edit_message_text(error_text, reply_markup=get_back_only_keyboard(user_id))
            return
        
        # 🔧 تغییر از games_played به total_wins
        if user_data['total_wins'] < MIN_WINS_FOR_WITHDRAWAL:
            remaining_wins = MIN_WINS_FOR_WITHDRAWAL - user_data['total_wins']
            
            error_text = f"🎮 {get_text(user_id, 'withdrawal_condition')}\n\n"
            error_text += f"⚠️ {get_text(user_id, 'min_wins_required')} {MIN_WINS_FOR_WITHDRAWAL} {get_text(user_id, 'wins_complete')}\n\n"
            error_text += f"📊 {get_text(user_id, 'your_wins')} {user_data['total_wins']}\n"
            error_text += f"⚡️ {get_text(user_id, 'remaining')} {remaining_wins}\n\n"
            error_text += f"🎯 {get_text(user_id, 'lets_play')}"
            
            await query.answer(f"❌ {remaining_wins} {get_text(user_id, 'more_wins_needed')}", show_alert=True)
            await query.edit_message_text(error_text, reply_markup=get_back_only_keyboard(user_id))
            return
        
        withdraw_text = f"💸 {get_text(user_id, 'withdraw_prizes')}\n\n"
        withdraw_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
        withdraw_text += f"🎁 {get_text(user_id, 'amazing_prizes')}\n\n"
        withdraw_text += f"✨ {get_text(user_id, 'choose_prize')}"
        
        await query.edit_message_text(withdraw_text, reply_markup=get_withdrawal_keyboard(user_id))
        return
    
    if data.startswith("withdraw_"):
        gift_type = data.split("_")[1]
        gift_data = WITHDRAWAL_OPTIONS.get(gift_type)
        
        if not gift_data:
            await query.answer(get_text(user_id, 'invalid_option'), show_alert=True)
            return
        
        required_amount = gift_data['amount']
        
        if user_data['balance'] < required_amount:
            shortage = required_amount - user_data['balance']
            await query.answer(f"{get_text(user_id, 'not_enough')} {shortage} ⭐ {get_text(user_id, 'shortage')}", show_alert=True)
            return
        
        context.user_data['withdrawal_gift'] = gift_type
        context.user_data['withdrawal_amount'] = required_amount
        context.user_data['waiting_for_withdrawal_id'] = True
        
        id_text = f"{get_text(user_id, 'send_id')}\n\n"
        id_text += f"{get_text(user_id, 'option')} {get_text(user_id, gift_type)}\n"
        id_text += f"{get_text(user_id, 'amount')} {required_amount} ⭐\n\n"
        id_text += f"{get_text(user_id, 'send_your_id')}\n\n"
        id_text += f"{get_text(user_id, 'example')}\n@username {get_text(user_id, 'or')} 123456789"
        
        await query.edit_message_text(id_text, reply_markup=get_back_only_keyboard(user_id))
        return
    
    if data == "referral":
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        referral_text = f"🎁 {get_text(user_id, 'referral_title')}\n\n"
        referral_text += f"✨ {get_text(user_id, 'per_friend')} {REFERRAL_REWARD} ⭐\n\n"
        referral_text += f"🔗 {get_text(user_id, 'your_link')}\n{referral_link}\n\n"
        referral_text += f"📊 {get_text(user_id, 'your_stats')}\n"
        referral_text += f"• {get_text(user_id, 'successful_invites')} {len(user_data.get('referrals', []))}\n"
        referral_text += f"• {get_text(user_id, 'total_income')} {len(user_data.get('referrals', []))*REFERRAL_REWARD} ⭐"
        
        await query.edit_message_text(referral_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if data == "support":
        context.user_data['waiting_for_support'] = True
        
        support_text = f"📞 {get_text(user_id, 'support_247')}\n\n"
        support_text += f"💬 {get_text(user_id, 'have_question')}\n\n"
        support_text += f"✍️ {get_text(user_id, 'write_message')}"
        
        await query.edit_message_text(support_text, reply_markup=get_back_only_keyboard(user_id))
        return
    
    if data == "admin_panel" and user_id == ADMIN_ID:
        admin_text = "👨‍💼 پنل مدیریت\n\n⚙️ یک گزینه را انتخاب کنید"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_users" and user_id == ADMIN_ID:
        total_users = len(users_db)
        blocked_users = sum(1 for u in users_db.values() if u.get('is_blocked', False))
        total_games = len(games_db)
        
        admin_text = f"👥 آمار کاربران\n\n"
        admin_text += f"📊 کل کاربران: {total_users}\n"
        admin_text += f"🚫 مسدود شده: {blocked_users}\n"
        admin_text += f"🎮 کل بازی‌ها: {total_games}"
        
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    # 🔧 جدید: جستجوی کاربر
    if data == "admin_search_user" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'search_user'
        admin_text = "🔍 جستجوی کاربر\n\n💬 ایدی کاربر را ارسال کنید:\n\n📝 مثال:\n123456789"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    # 🔧 جدید: نمایش جزئیات کاربر
    if data.startswith("admin_user_detail_") and user_id == ADMIN_ID:
        target_user_id = int(data.split("_")[3])
        
        if target_user_id not in users_db:
            await query.answer("❌ کاربر یافت نشد!", show_alert=True)
            return
        
        target_user = users_db[target_user_id]
        
        detail_text = f"👤 جزئیات کاربر\n\n"
        detail_text += f"🆔 آیدی: {target_user_id}\n"
        detail_text += f"👤 یوزرنیم: @{target_user.get('username', 'ندارد')}\n"
        detail_text += f"💰 موجودی: {target_user['balance']} ⭐\n\n"
        
        detail_text += f"🎮 آمار بازی‌ها:\n"
        detail_text += f"• کل بازی‌ها: {target_user['games_played']}\n"
        detail_text += f"• برد: {target_user['total_wins']}\n"
        detail_text += f"• باخت: {target_user['total_losses']}\n"
        
        if target_user['games_played'] > 0:
            win_rate = (target_user['total_wins'] / target_user['games_played']) * 100
            detail_text += f"• نرخ برد: {win_rate:.1f}%\n"
        
        detail_text += f"\n🎁 دعوت‌ها:\n"
        detail_text += f"• تعداد دعوت‌ها: {len(target_user.get('referrals', []))}\n"
        detail_text += f"• درآمد دعوت: {len(target_user.get('referrals', []))*REFERRAL_REWARD} ⭐\n"
        
        if target_user.get('referred_by'):
            detail_text += f"• دعوت شده توسط: {target_user['referred_by']}\n"
        
        detail_text += f"\n⚙️ وضعیت: {'🚫 مسدود' if target_user.get('is_blocked') else '✅ فعال'}"
        
        await query.edit_message_text(detail_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_stars_stats" and user_id == ADMIN_ID:
        total_balance = sum(u['balance'] for u in users_db.values())
        net_profit = total_stars_lost - total_stars_earned
        
        stars_text = "⭐ آمار Stars\n\n"
        stars_text += "📊 آمار کلی سیستم:\n\n"
        stars_text += f"✅ کل Stars کسب شده: {total_stars_earned} ⭐\n"
        stars_text += f"❌ کل Stars از دست رفته: {total_stars_lost} ⭐\n"
        stars_text += f"💎 سود خالص سیستم: {net_profit} ⭐\n"
        stars_text += f"💰 کل موجودی کاربران: {total_balance} ⭐\n\n"
        
        if total_stars_earned + total_stars_lost > 0:
            earned_percent = (total_stars_earned / (total_stars_earned + total_stars_lost)) * 100
            lost_percent = 100 - earned_percent
            stars_text += f"📈 نمودار:\n"
            stars_text += f"✅ برد: {earned_percent:.1f}%\n"
            stars_text += f"❌ باخت: {lost_percent:.1f}%"
        
        await query.edit_message_text(stars_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_reset_stars_stats" and user_id == ADMIN_ID:
        total_stars_earned = 0
        total_stars_lost = 0
        
        reset_text = "🔄 بازیابی آمار\n\n"
        reset_text += "✅ آمار Stars با موفقیت بازیابی شد!\n\n"
        reset_text += "📊 آمار جدید:\n\n"
        reset_text += "✅ کل Stars کسب شده: 0 ⭐\n"
        reset_text += "❌ کل Stars از دست رفته: 0 ⭐\n"
        reset_text += "💎 سود خالص سیستم: 0 ⭐"
        
        await query.edit_message_text(reset_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_games" and user_id == ADMIN_ID:
        recent_games = games_db[-10:] if len(games_db) > 10 else games_db
        
        games_text = "🎮 آخرین بازی‌ها\n\n"
        
        for game in reversed(recent_games):
            result = "✅" if game['won'] else "❌"
            username = game.get('username', 'unknown')
            games_text += f"{result} @{username}\n"
            games_text += f"{game['game_type']} │ {game['bet_amount']} ⭐\n\n"
        
        if not recent_games:
            games_text += "هیچ بازی‌ای ثبت نشده"
        
        await query.edit_message_text(games_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_add_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'add_balance'
        admin_text = "➕ افزایش موجودی\n\n💬 فرمت ارسال:\n\nایدی_کاربر مبلغ\n\n📝 مثال:\n123456789 100"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_reduce_balance" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'reduce_balance'
        admin_text = "➖ کاهش موجودی\n\n💬 فرمت ارسال:\n\nایدی_کاربر مبلغ\n\n📝 مثال:\n123456789 50"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_block" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'block_user'
        admin_text = "🚫 بلاک کاربر\n\n💬 ایدی کاربر را ارسال کنید:\n\n📝 مثال:\n123456789"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_unblock" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'unblock_user'
        admin_text = "✅ آنبلاک کاربر\n\n💬 ایدی کاربر را ارسال کنید:\n\n📝 مثال:\n123456789"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_withdrawals" and user_id == ADMIN_ID:
        pending_withdrawals = [w for w in withdrawals_db if w.get('status') == 'pending']
        
        withdrawal_text = "📋 درخواست‌های برداشت\n\n"
        
        if not pending_withdrawals:
            withdrawal_text += "هیچ درخواستی وجود ندارد"
        else:
            for w in pending_withdrawals:
                gift_type = w.get('gift_type', 'teddy')
                gift_name = get_text(user_id, gift_type)
                withdrawal_text += f"👤 {w['username']}\n"
                withdrawal_text += f"🆔 {w['user_id']}\n"
                withdrawal_text += f"🎁 {gift_name}\n"
                withdrawal_text += f"💰 {w['amount']} ⭐\n"
                withdrawal_text += f"📝 آیدی: {w['withdrawal_id']}\n\n"
        
        await query.edit_message_text(withdrawal_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'broadcast'
        admin_text = "📢 ارسال همگانی\n\n💬 پیام خود را ارسال کنید\n\n⚡️ به تمام کاربران ارسال می‌شود"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_send_user" and user_id == ADMIN_ID:
        context.user_data['admin_action'] = 'send_user'
        admin_text = "💬 ارسال خصوصی\n\n💬 فرمت ارسال:\n\nایدی_کاربر پیام\n\n📝 مثال:\n123456789 سلام"
        await query.edit_message_text(admin_text, reply_markup=get_admin_keyboard())
        return
    
    # 🔧 اصلاح: ریست کردن wins بعد از تایید برداشت
    if data.startswith("approve_withdrawal_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[2])
        withdrawal_index = int(parts[3])
        
        try:
            approval_text = "✅ برداشت شما تایید شد!\n\n"
            approval_text += "🎁 هدیه شما در حال ارسال است\n"
            approval_text += "💌 به زودی دریافت خواهید کرد!"
            
            await context.bot.send_message(chat_id=target_user_id, text=approval_text)
            
            # 🔧 اصلاح: ریست کردن total_wins به 0
            if target_user_id in users_db:
                users_db[target_user_id]['total_wins'] = 0
                logger.info(f"✅ User {target_user_id} wins reset to 0 after withdrawal approval")
            
            if withdrawal_index < len(withdrawals_db):
                withdrawals_db[withdrawal_index]['status'] = 'approved'
            
            await query.edit_message_text(
                text=query.message.text + "\n\n✅ تایید شد و به کاربر اطلاع داده شد\n🔄 برد های کاربر به 0 بازنشانی شد",
                reply_markup=None
            )
        except Exception as e:
            await query.answer(f"❌ خطا: {str(e)}", show_alert=True)
        return
    
    if data == "back_to_main":
        context.user_data.clear()
        
        user_data = get_user(user_id)
        back_text = f"🎮 {get_text(user_id, 'hello')} {query.from_user.first_name}!\n\n"
        back_text += f"💰 {get_text(user_id, 'your_wallet')} {user_data['balance']} ⭐\n\n"
        back_text += f"🎯 {get_text(user_id, 'ready_to_win')}"
        
        await query.edit_message_text(back_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('waiting_for_custom_bet'):
        try:
            bet_amount = int(text.strip())
            
            if bet_amount < MIN_BET:
                error_text = f"{get_text(user_id, 'min_amount')} {MIN_BET} ⭐ {get_text(user_id, 'be')}\n\n"
                error_text += get_text(user_id, 'enter_again')
                await update.message.reply_text(error_text)
                return
            
            user_data = get_user(user_id)
            if user_data['balance'] < bet_amount:
                error_text = f"{get_text(user_id, 'insufficient_balance')}\n\n"
                error_text += f"{get_text(user_id, 'your_balance')} {user_data['balance']} ⭐\n"
                error_text += f"{get_text(user_id, 'requested')} {bet_amount} ⭐"
                await update.message.reply_text(error_text)
                return
            
            game_type = context.user_data.get('current_game', 'football')
            context.user_data['waiting_for_custom_bet'] = False
            
            try:
                await update.message.delete()
            except:
                pass
            
            game_message_id = context.user_data.get('game_message_id')
            if game_message_id:
                loading_text = f"⏳ {get_text(user_id, game_type)}\n\n"
                loading_text += f"{get_text(user_id, 'game_in_progress')}\n\n"
                loading_text += f"{get_text(user_id, 'bet')} {bet_amount} ⭐"
                
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=game_message_id,
                    text=loading_text
                )
            
            game_emoji = GAME_EMOJI_MAP.get(game_type, DiceEmoji.DICE)
            dice_message = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=game_emoji)
            
            await asyncio.sleep(4)
            
            dice_value = dice_message.dice.value
            win = dice_value in WINNING_CONDITIONS.get(game_type, [6])
            
            await update_balance(user_id, -bet_amount, context, send_notification=False)
            
            if win:
                reward = bet_amount * 2
                await update_balance(user_id, reward, context, f"{get_text(user_id, 'game')}: {get_text(user_id, game_type)}", send_notification=False)
                
                result_text = f"{get_text(user_id, 'you_won')}\n\n"
                result_text += f"{get_text(user_id, 'game')} {get_text(user_id, game_type)}\n"
                result_text += f"{get_text(user_id, 'result')} {dice_value}\n\n"
                result_text += f"{get_text(user_id, 'bet')} {bet_amount} ⭐\n"
                result_text += f"{get_text(user_id, 'prize')} {reward} ⭐"
                
                users_db[user_id]["total_wins"] += 1
                users_db[user_id]["games_played"] += 1
            else:
                result_text = f"{get_text(user_id, 'you_lost')}\n\n"
                result_text += f"{get_text(user_id, 'game')} {get_text(user_id, game_type)}\n"
                result_text += f"{get_text(user_id, 'result')} {dice_value}\n\n"
                result_text += f"{get_text(user_id, 'lost')} {bet_amount} ⭐\n\n"
                result_text += get_text(user_id, 'dont_give_up')
                
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
            result_text += f"\n\n{get_text(user_id, 'new_balance')} {updated_user['balance']} ⭐"
            
            if game_message_id:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=game_message_id,
                    text=result_text,
                    reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID)
                )
            else:
                await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=result_text,
                    reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID)
                )
            return
            
        except ValueError:
            await update.message.reply_text(f"{get_text(user_id, 'only_number')}\n\n{get_text(user_id, 'example')} 25")
            return
    
    if context.user_data.get('waiting_for_withdrawal_id'):
        user_data = get_user(user_id)
        gift_type = context.user_data.get('withdrawal_gift')
        withdrawal_amount = context.user_data.get('withdrawal_amount')
        
        users_db[user_id]['balance'] -= withdrawal_amount
        
        withdrawal_data = {
            "user_id": user_id,
            "username": update.effective_user.username,
            "amount": withdrawal_amount,
            "gift_type": gift_type,
            "gift_name": get_text(user_id, gift_type),
            "withdrawal_id": text,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        withdrawals_db.append(withdrawal_data)
        
        try:
            admin_notif = "🔔 درخواست برداشت جدید\n\n"
            admin_notif += f"👤 @{update.effective_user.username or 'بدون_یوزرنیم'}\n"
            admin_notif += f"🆔 {user_id}\n"
            admin_notif += f"🎁 {get_text(user_id, gift_type)}\n"
            admin_notif += f"💰 {withdrawal_amount} ⭐\n\n"
            admin_notif += f"📝 آیدی واریز:\n{text}"
            
            keyboard = [[InlineKeyboardButton("✅ تایید و ارسال به کاربر", callback_data=f"approve_withdrawal_{user_id}_{len(withdrawals_db)-1}")]]
            
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notif, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
        
        context.user_data['waiting_for_withdrawal_id'] = False
        context.user_data.pop('withdrawal_gift', None)
        context.user_data.pop('withdrawal_amount', None)
        
        success_text = f"{get_text(user_id, 'request_submitted')}\n\n"
        success_text += f"💰 {withdrawal_amount} ⭐ {get_text(user_id, 'deducted')}\n\n"
        success_text += f"{get_text(user_id, 'team_reviewing')}\n\n"
        success_text += get_text(user_id, 'thanks')
        
        await update.message.reply_text(success_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if context.user_data.get('waiting_for_support'):
        try:
            support_notif = "📞 پیام پشتیبانی جدید\n\n"
            support_notif += f"👤 @{update.effective_user.username or 'بدون_یوزرنیم'}\n"
            support_notif += f"🆔 {user_id}\n\n"
            support_notif += f"💬 پیام:\n{text}"
            
            await context.bot.send_message(chat_id=ADMIN_ID, text=support_notif)
            
            context.user_data['waiting_for_support'] = False
            
            success_text = f"{get_text(user_id, 'sent')}\n\n"
            success_text += f"{get_text(user_id, 'message_sent_support')}\n\n"
            success_text += get_text(user_id, 'will_reply_soon')
            
            await update.message.reply_text(success_text, reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        except Exception as e:
            logger.error(f"Error sending support message: {e}")
            await update.message.reply_text(get_text(user_id, 'send_error'), reply_markup=get_main_keyboard(user_id, user_id == ADMIN_ID))
        return
    
    if user_id == ADMIN_ID:
        admin_action = context.user_data.get('admin_action')
        
        # 🔧 جدید: جستجوی کاربر
        if admin_action == 'search_user':
            try:
                target_user_id = int(text.strip())
                
                if target_user_id not in users_db:
                    await update.message.reply_text("❌ کاربر یافت نشد!")
                    context.user_data['admin_action'] = None
                    return
                
                target_user = users_db[target_user_id]
                
                detail_text = f"👤 جزئیات کاربر\n\n"
                detail_text += f"🆔 آیدی: {target_user_id}\n"
                detail_text += f"👤 یوزرنیم: @{target_user.get('username', 'ندارد')}\n"
                detail_text += f"💰 موجودی: {target_user['balance']} ⭐\n\n"
                
                detail_text += f"🎮 آمار بازی‌ها:\n"
                detail_text += f"• کل بازی‌ها: {target_user['games_played']}\n"
                detail_text += f"• برد: {target_user['total_wins']}\n"
                detail_text += f"• باخت: {target_user['total_losses']}\n"
                
                if target_user['games_played'] > 0:
                    win_rate = (target_user['total_wins'] / target_user['games_played']) * 100
                    detail_text += f"• نرخ برد: {win_rate:.1f}%\n"
                
                detail_text += f"\n🎁 دعوت‌ها:\n"
                detail_text += f"• تعداد دعوت‌ها: {len(target_user.get('referrals', []))}\n"
                detail_text += f"• درآمد دعوت: {len(target_user.get('referrals', []))*REFERRAL_REWARD} ⭐\n"
                
                if target_user.get('referrals'):
                    detail_text += f"• لیست دعوت شده‌ها: {', '.join(map(str, target_user['referrals']))}\n"
                
                if target_user.get('referred_by'):
                    detail_text += f"• دعوت شده توسط: {target_user['referred_by']}\n"
                
                detail_text += f"\n⚙️ وضعیت: {'🚫 مسدود' if target_user.get('is_blocked') else '✅ فعال'}"
                
                await update.message.reply_text(detail_text, reply_markup=get_admin_keyboard())
                context.user_data['admin_action'] = None
            except ValueError:
                await update.message.reply_text("❌ فرمت نادرست! لطفاً فقط عدد وارد کنید.")
            return
        
        if admin_action == 'add_balance':
            try:
                parts = text.strip().split()
                target_user_id = int(parts[0])
                amount = int(parts[1])
                
                await update_balance(target_user_id, amount, context, "افزایش توسط ادمین")
                
                success_text = f"✅ انجام شد!\n\n🆔 {target_user_id}\n➕ {amount} ⭐"
                await update.message.reply_text(success_text, reply_markup=get_admin_keyboard())
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
                
                success_text = f"✅ انجام شد!\n\n🆔 {target_user_id}\n➖ {amount} ⭐"
                await update.message.reply_text(success_text, reply_markup=get_admin_keyboard())
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789 50")
            return
        
        elif admin_action == 'block_user':
            try:
                target_user_id = int(text.strip())
                if target_user_id in users_db:
                    users_db[target_user_id]['is_blocked'] = True
                    await update.message.reply_text(f"✅ کاربر {target_user_id} مسدود شد", reply_markup=get_admin_keyboard())
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
                    await update.message.reply_text(f"✅ کاربر {target_user_id} آزاد شد", reply_markup=get_admin_keyboard())
                else:
                    await update.message.reply_text("❌ کاربر پیدا نشد!")
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789")
            return
        
        elif admin_action == 'broadcast':
            success_count = 0
            fail_count = 0
            
            broadcast_msg = f"📢 پیام مدیریت\n\n{text}"
            
            for uid in users_db.keys():
                try:
                    await context.bot.send_message(chat_id=uid, text=broadcast_msg)
                    success_count += 1
                except:
                    fail_count += 1
            
            result_text = f"✅ ارسال شد!\n\n📊 موفق: {success_count}\n❌ ناموفق: {fail_count}"
            await update.message.reply_text(result_text, reply_markup=get_admin_keyboard())
            context.user_data['admin_action'] = None
            return
        
        elif admin_action == 'send_user':
            try:
                parts = text.strip().split(maxsplit=1)
                target_user_id = int(parts[0])
                message = parts[1]
                
                personal_msg = f"📬 پیام مدیریت\n\n{message}"
                await context.bot.send_message(chat_id=target_user_id, text=personal_msg)
                
                await update.message.reply_text(f"✅ پیام به {target_user_id} ارسال شد", reply_markup=get_admin_keyboard())
                context.user_data['admin_action'] = None
            except:
                await update.message.reply_text("❌ فرمت نادرست!\n\n📝 مثال: 123456789 سلام")
            return

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ ربات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
