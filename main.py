import os
import telebot
from telebot import types
from datetime import datetime
import secrets
from urllib.parse import quote
from threading import Thread
from flask import Flask
from supabase import create_client, Client

TOKEN = "8986245388:AAHAnAMAJ0cilInRubAPashTrigEpAeli74"

SUPPORT_ID = "@Behrad_BNB"
DAILY_REWARD = 3
WELCOME_BONUS = 5
REF_REWARD = 5
FORCE_CHANNEL = "@playli3tet"
FORCE_LINK = "https://t.me/playli3tet"

SUPABASE_URL = "https://vnhmtrluomsgspjfxjmk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZuaG10cmx1b21zZ3NwamZ4am1rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIzNDk3MjgsImV4cCI6MjEwNzkyNTcyOH0.3juM52lCY8UqPjAzpU_J8d-VGTi_6ulm_TQ0X4OPZNs"

bot = telebot.TeleBot(TOKEN, threaded=False)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

def make_public_id():
    while True:
        code = "".join(secrets.choice("0123456789") for _ in range(10))
        res = supabase.table("users").select("user_id").eq("public_id", code).execute()
        if len(res.data) == 0:
            return code

def ensure_user(uid, tg_user=None):
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    is_new = len(res.data) == 0

    if is_new:
        supabase.table("users").insert({
            "user_id": uid,
            "coins": WELCOME_BONUS,
            "public_id": make_public_id(),
            "joined_at": datetime.now().isoformat(),
            "language": "fa",
            "referral_paid": 0,
            "invite_count": 0,
            "order_notify": 1,
            "general_notify": 1,
            "system_notify": 1,
            "contest_notify": 1
        }).execute()
    else:
        user_data = res.data[0]
        if not user_data.get("public_id"):
            supabase.table("users").update({"public_id": make_public_id()}).eq("user_id", uid).execute()
        if not user_data.get("joined_at"):
            supabase.table("users").update({"joined_at": datetime.now().isoformat()}).eq("user_id", uid).execute()

    if tg_user is not None:
        supabase.table("users").update({"username": tg_user.username}).eq("user_id", uid).execute()

    return is_new

def get_user(uid):
    ensure_user(uid)
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    return res.data[0] if res.data else None

def get_coins(uid):
    row = get_user(uid)
    return row.get("coins", 0) if row and row.get("coins") is not None else 0

def get_lang(uid):
    row = get_user(uid)
    return "en" if row and row.get("language") == "en" else "fa"

def tx(uid, fa, en):
    return en if get_lang(uid) == "en" else fa

def notify_on(uid, column):
    row = get_user(uid)
    return row.get(column, 1) == 1 if row else True

def is_joined(uid):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, uid)
        if member.status in ["creator", "administrator", "member"]:
            return True
        if member.status == "restricted":
            return getattr(member, "is_member", False)
        return False
    except:
        return False

def main_keyboard(uid):
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if get_lang(uid) == "en":
        mk.row(types.KeyboardButton("🧾 Order"), types.KeyboardButton("🪙 Collect coins"))
        mk.row(types.KeyboardButton("🎁 Daily coins"), types.KeyboardButton("👥 Invite friends"))
        mk.row(types.KeyboardButton("👤 Account"), types.KeyboardButton("📞 Support"))
    else:
        mk.row(types.KeyboardButton("🧾 ثبت سفارش"), types.KeyboardButton("🪙 جمع آوری سکه"))
        mk.row(types.KeyboardButton("🎁 سکه روزانه"), types.KeyboardButton("👥 دعوت دوستان"))
        mk.row(types.KeyboardButton("👤 حساب"), types.KeyboardButton("📞 پشتیبانی"))
    return mk

def force_keyboard(uid):
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "📢 عضو شدن در کانال", "📢 Join channel"), url=FORCE_LINK))
    mk.add(types.InlineKeyboardButton(tx(uid, "✅ عضو شدم، بررسی کن", "✅ I joined, check"), callback_data="check_join"))
    return mk

def back_keyboard(uid):
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 برگشت", "🔙 Back"), callback_data="back"))
    return mk

def send_welcome(chat_id, uid):
    coins = get_coins(uid)
    text = tx(uid, f"👋 سلام! خوش اومدی\n💰 موجودی: {coins} سکه", f"👋 Welcome!\n💰 Balance: {coins} coins")
    bot.send_message(chat_id, text, reply_markup=main_keyboard(uid))

def send_main(chat_id, uid):
    coins = get_coins(uid)
    text = tx(uid, f"🏠 منوی اصلی\n💰 موجودی: {coins} سکه", f"🏠 Main menu\n💰 Balance: {coins} coins")
    bot.send_message(chat_id, text, reply_markup=main_keyboard(uid))

def send_force(chat_id, uid):
    text = tx(
        uid,
        f"⛔ اول باید عضو کانال ما بشی!\n\n{FORCE_LINK}\n\nبعد از عضویت دکمه بررسی را بزن.",
        f"⛔ Join our channel first!\n\n{FORCE_LINK}\n\nThen press check."
    )
    bot.send_message(chat_id, text, reply_markup=force_keyboard(uid))

def do_daily(chat_id, uid):
    user = get_user(uid)
    coins = user.get("coins", 0)
    last_daily = user.get("last_daily")
    now = datetime.now()

    if last_daily:
        try:
            old = datetime.fromisoformat(last_daily)
            passed = (now - old).total_seconds()
            if passed < 86400:
                remain = int(86400 - passed)
                hours, minutes = remain // 3600, (remain % 3600) // 60
                text = tx(
                    uid,
                    f"⏳ امروز سکه گرفتی!\n{hours} ساعت و {minutes} دقیقه دیگه بیا.\n💰 موجودی: {coins}",
                    f"⏳ You got daily coins today!\nCome back in {hours}h {minutes}m.\n💰 Balance: {coins}"
                )
                bot.send_message(chat_id, text, reply_markup=back_keyboard(uid))
                return
        except:
            pass

    new_coins = coins + DAILY_REWARD
    supabase.table("users").update({"coins": new_coins, "last_daily": now.isoformat()}).eq("user_id", uid).execute()
    bot.send_message(
        chat_id,
        tx(
            uid,
            f"🎁 {DAILY_REWARD} سکه روزانه گرفتی!\n💰 موجودی جدید: {new_coins}",
            f"🎁 You got {DAILY_REWARD} daily coins!\n💰 New balance: {new_coins}"
        ),
        reply_markup=back_keyboard(uid)
    )

def do_support(chat_id, uid):
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "📞 ارتباط با پشتیبانی", "📞 Contact support"), url="https://t.me/Behrad_BNB"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 برگشت", "🔙 Back"), callback_data="back"))
    bot.send_message(
        chat_id,
        tx(uid, f"📞 بخش پشتیبانی\nپیام بده به:\n{SUPPORT_ID}", f"📞 Support\nContact:\n{SUPPORT_ID}"),
        reply_markup=mk
    )

def process_referral(uid):
    if not is_joined(uid):
        return
    user = get_user(uid)
    inviter = user.get("invited_by")
    paid = user.get("referral_paid", 0)
    if inviter is None or paid == 1 or inviter == uid:
        return

    inviter_res = supabase.table("users").select("user_id", "coins", "invite_count").eq("user_id", inviter).execute()
    if len(inviter_res.data) == 0:
        return

    inv_data = inviter_res.data[0]
    new_coins = (inv_data.get("coins", 0) or 0) + REF_REWARD
    new_invite_count = (inv_data.get("invite_count", 0) or 0) + 1
    supabase.table("users").update({"coins": new_coins, "invite_count": new_invite_count}).eq("user_id", inviter).execute()
    supabase.table("users").update({"referral_paid": 1}).eq("user_id", uid).execute()

    if notify_on(inviter, "general_notify"):
        try:
            bot.send_message(
                inviter,
                tx(
                    inviter,
                    f"🎉 تبریک!\nیک نفر با لینک تو اومد و عضو اجباری شد.\n💰 {REF_REWARD} سکه جایزه گرفتی.",
                    f"🎉 Congratulations!\nSomeone joined with your link.\n💰 You got {REF_REWARD} coins."
                )
            )
        except:
            pass

def do_invite(chat_id, uid):
    try:
        username = bot.get_me().username
    except:
        username = None
    if not username:
        bot.send_message(chat_id, "Error")
        return

    user = get_user(uid)
    link = f"https://t.me/{username}?start={uid}"
    share_link = f"https://t.me/share/url?url={quote(link, safe='')}"
    text = tx(
        uid,
        f"👥 دعوت دوستان\n\nبرای هر دوستی که با لینک تو بیاد و عضو اجباری بشه:\n🎁 {REF_REWARD} سکه جایزه می‌گیری.\n\n👤 دعوت موفق: {user.get('invite_count', 0)}\n\n🔗 لینک اختصاصی تو:\n{link}",
        f"👥 Invite friends\n\nFor every friend who joins with your link:\n🎁 You get {REF_REWARD} coins.\n\n👤 Successful invites: {user.get('invite_count', 0)}\n\n🔗 Your invite link:\n{link}"
    )
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "📤 اشتراک گذاری لینک", "📤 Share link"), url=share_link))
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 برگشت", "🔙 Back"), callback_data="back"))
    bot.send_message(chat_id, text, reply_markup=mk)

def send_account(chat_id, uid):
    user = get_user(uid)
    orders_res = supabase.table("orders").select("*", count="exact").eq("user_id", uid).execute()
    orders_count = orders_res.count if orders_res.count else 0
    channels_res = supabase.table("channels").select("*", count="exact").eq("owner_id", uid).execute()
    channels_count = channels_res.count if channels_res.count else 0
    collects_res = supabase.table("collects").select("*", count="exact").eq("user_id", uid).execute()
    collects_count = collects_res.count if collects_res.count else 0
    username = f"@{user.get('username')}" if user.get("username") else "—"
    join_date = str(user.get("joined_at", "")).split("T")[0]
    text = tx(
        uid,
        f"✨ صفحه حساب کاربری ✨\n━━━━━━━━━━━━\n\n🆔 شناسه عددی شما: {user.get('public_id')}\n🔗 یوزرنیم شما: {username}\n\n💰 موجودی: {user.get('coins', 0)} سکه\n🧾 مجموع سفارش‌ها: {orders_count}\n📁 کانال‌های ثبت‌شده: {channels_count}\n👥 عضویت‌های جمع‌آوری: {collects_count}\n\n📅 تاریخ عضویت: {join_date}",
        f"✨ Account ✨\n━━━━━━━━━━━━\n\n🆔 Account ID: {user.get('public_id')}\n🔗 Username: {username}\n\n💰 Balance: {user.get('coins', 0)}\n🧾 Orders: {orders_count}\n📁 Channels: {channels_count}\n👥 Collections: {collects_count}\n\n📅 Join date: {join_date}"
    )
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "⚙️ تنظیمات", "⚙️ Settings"), callback_data="settings"))
    bot.send_message(chat_id, text, reply_markup=mk)

def send_settings(chat_id, uid):
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "🔔 تنظیمات اعلان‌ها", "🔔 Notifications"), callback_data="notifications"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🌐 تغییر زبان", "🌐 Change language"), callback_data="languages"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🏠 منوی اصلی", "🏠 Main menu"), callback_data="back"))
    bot.send_message(chat_id, tx(uid, "⚙️ تنظیمات\n\nحساب کاربری خود را مدیریت کنید.", "⚙️ Settings\n\nManage your account."), reply_markup=mk)

def notify_status(uid, column):
    return tx(uid, "فعال ✅", "Active ✅") if notify_on(uid, column) else tx(uid, "غیرفعال ❌", "Inactive ❌")

def send_notifications(chat_id, uid):
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "📈 تکمیل سفارش: ", "📈 Order completion: ") + notify_status(uid, "order_notify"), callback_data="notify_order"))
    mk.add(types.InlineKeyboardButton(tx(uid, "📢 پیام همگانی: ", "📢 General messages: ") + notify_status(uid, "general_notify"), callback_data="notify_general"))
    mk.add(types.InlineKeyboardButton(tx(uid, "⚠️ هشدارهای سیستمی: ", "⚠️ System warnings: ") + notify_status(uid, "system_notify"), callback_data="notify_system"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🏆 رقابت ماهانه: ", "🏆 Monthly contest: ") + notify_status(uid, "contest_notify"), callback_data="notify_contest"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 بازگشت به تنظیمات", "🔙 Back to settings"), callback_data="settings"))
    bot.send_message(chat_id, tx(uid, "🔔 تنظیمات اعلان‌ها\n\nمشخص کنید کدام اعلان‌ها را دریافت کنید.", "🔔 Notification settings\n\nChoose notifications."), reply_markup=mk)

def send_languages(chat_id, uid):
    mk = types.InlineKeyboardMarkup()
    current = get_lang(uid)
    fa_mark = " ✅" if current == "fa" else ""
    en_mark = " ✅" if current == "en" else ""
    mk.add(types.InlineKeyboardButton(f"🇮🇷 فارسی{fa_mark}", callback_data="lang_fa"))
    mk.add(types.InlineKeyboardButton(f"🇬🇧 English{en_mark}", callback_data="lang_en"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 بازگشت به تنظیمات", "🔙 Back to settings"), callback_data="settings"))
    bot.send_message(chat_id, tx(uid, "🌐 زبان خود را انتخاب کنید:", "🌐 Select your language:"), reply_markup=mk)

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    args = message.text.split()
    is_new = ensure_user(uid, message.from_user)

    if is_new and len(args) > 1:
        try:
            inviter = int(args[1])
            supabase.table("users").update({"invited_by": inviter}).eq("user_id", uid).execute()
        except:
            pass

    if not is_joined(uid):
        send_force(message.chat.id, uid)
        return

    process_referral(uid)
    send_welcome(message.chat.id, uid)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check(call):
    uid = call.from_user.id
    if is_joined(uid):
        process_referral(uid)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_welcome(call.message.chat.id, uid)
    else:
        bot.answer_callback_query(call.id, "❌ هنوز عضو نشدی!")

@bot.callback_query_handler(func=lambda call: call.data == "back")
def callback_back(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_main(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "settings")
def callback_settings(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_settings(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "notifications")
def callback_notifications(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_notifications(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "languages")
def callback_languages(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_languages(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("notify_"))
def callback_notify_toggle(call):
    uid = call.from_user.id
    col = call.data.replace("notify_", "") + "_notify"
    user = get_user(uid)
    new_val = 0 if user.get(col, 1) == 1 else 1
    supabase.table("users").update({col: new_val}).eq("user_id", uid).execute()
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_notifications(call.message.chat.id, uid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def callback_lang_set(call):
    uid = call.from_user.id
    lang = call.data.replace("lang_", "")
    supabase.table("users").update({"language": lang}).eq("user_id", uid).execute()
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_settings(call.message.chat.id, uid)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    uid = message.from_user.id
    text = message.text or ""

    if not is_joined(uid):
        send_force(message.chat.id, uid)
        return

    if text in ["🎁 سکه روزانه", "🎁 Daily coins"]:
        do_daily(message.chat.id, uid)
    elif text in ["📞 پشتیبانی", "📞 Support"]:
        do_support(message.chat.id, uid)
    elif text in ["👥 دعوت دوستان", "👥 Invite friends"]:
        do_invite(message.chat.id, uid)
    elif text in ["👤 حساب", "👤 Account"]:
        send_account(message.chat.id, uid)
    else:
        send_main(message.chat.id, uid)

print("Bot is running...")
keep_alive()
bot.infinity_polling()
