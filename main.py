import telebot
from telebot import types
import sqlite3
from datetime import datetime
import time
import secrets
from urllib.parse import quote

TOKEN = "8986245388:AAHAnAMAJ0cilInRubAPashTrigEpAeli74"

SUPPORT_ID = "@Behrad_BNB"

DAILY_REWARD = 3
WELCOME_BONUS = 5
REF_REWARD = 5
MAX_ORDER = 500

FORCE_CHANNEL = "@playli3tet"
FORCE_LINK = "https://t.me/playli3tet"

bot = telebot.TeleBot(TOKEN, threaded=False)

states = {}

db = sqlite3.connect(
    "bot.db",
    check_same_thread=False
)

db.row_factory = sqlite3.Row


# ============== DATABASE ==============

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    last_daily TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    chat_id TEXT,
    title TEXT,
    link TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    channel_db_id INTEGER,
    need_count INTEGER DEFAULT 0,
    done_count INTEGER DEFAULT 0,
    date TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS collects (
    user_id INTEGER,
    channel_db_id INTEGER,
    PRIMARY KEY(user_id, channel_db_id)
)
""")

db.commit()


def has_col(table, col):
    rows = db.execute(
        "PRAGMA table_info(" + table + ")"
    ).fetchall()

    for row in rows:
        if row["name"] == col:
            return True

    return False


def add_col(table, col, definition):
    if not has_col(table, col):
        try:
            db.execute(
                "ALTER TABLE " + table +
                " ADD COLUMN " + col +
                " " + definition
            )
            db.commit()
        except:
            pass


add_col("users", "username", "TEXT")
add_col("users", "public_id", "TEXT")
add_col("users", "joined_at", "TEXT")
add_col("users", "language", "TEXT DEFAULT 'fa'")
add_col("users", "invited_by", "INTEGER")
add_col("users", "referral_paid", "INTEGER DEFAULT 0")
add_col("users", "invite_count", "INTEGER DEFAULT 0")
add_col("users", "order_notify", "INTEGER DEFAULT 1")
add_col("users", "general_notify", "INTEGER DEFAULT 1")
add_col("users", "system_notify", "INTEGER DEFAULT 1")
add_col("users", "contest_notify", "INTEGER DEFAULT 1")

add_col("orders", "completed_notified", "INTEGER DEFAULT 0")

db.execute("""
UPDATE users
SET coins=COALESCE(coins, 0),
    invite_count=COALESCE(invite_count, 0),
    referral_paid=COALESCE(referral_paid, 0),
    order_notify=COALESCE(order_notify, 1),
    general_notify=COALESCE(general_notify, 1),
    system_notify=COALESCE(system_notify, 1),
    contest_notify=COALESCE(contest_notify, 1),
    language=COALESCE(language, 'fa')
""")

db.execute("""
UPDATE orders
SET need_count=COALESCE(need_count, 0),
    done_count=COALESCE(done_count, 0),
    completed_notified=COALESCE(completed_notified, 0)
""")

db.commit()


# ============== USERS ==============

def make_public_id():
    while True:
        code = ""

        for i in range(10):
            code += secrets.choice("0123456789")

        row = db.execute(
            "SELECT user_id FROM users WHERE public_id=?",
            (code,)
        ).fetchone()

        if row is None:
            return code


def ensure_user(uid, tg_user=None):
    old = db.execute(
        "SELECT * FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()

    is_new = old is None

    if is_new:
        db.execute("""
        INSERT INTO users(
            user_id,
            coins,
            public_id,
            joined_at,
            language,
            referral_paid,
            invite_count,
            order_notify,
            general_notify,
            system_notify,
            contest_notify
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid,
            WELCOME_BONUS,
            make_public_id(),
            datetime.now().isoformat(),
            "fa",
            0,
            0,
            1,
            1,
            1,
            1
        ))

    else:
        if old["public_id"] is None:
            db.execute(
                "UPDATE users SET public_id=? WHERE user_id=?",
                (make_public_id(), uid)
            )

        if old["joined_at"] is None:
            db.execute(
                "UPDATE users SET joined_at=? WHERE user_id=?",
                (datetime.now().isoformat(), uid)
            )

    if tg_user is not None:
        db.execute(
            "UPDATE users SET username=? WHERE user_id=?",
            (tg_user.username, uid)
        )

    db.commit()

    return is_new


def get_user(uid):
    ensure_user(uid)

    return db.execute(
        "SELECT * FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()


def get_coins(uid):
    row = get_user(uid)

    if row["coins"] is None:
        return 0

    return row["coins"]


def get_lang(uid):
    row = get_user(uid)

    if row["language"] == "en":
        return "en"

    return "fa"


def tx(uid, fa, en):
    if get_lang(uid) == "en":
        return en

    return fa


def notify_on(uid, column):
    row = get_user(uid)

    return row[column] == 1


# ============== HELPERS ==============

digit_map = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789"
)


def parse_number(text):
    text = text.strip().translate(digit_map)

    if text.isdigit():
        return int(text)

    return None


def get_channel_username(link):
    link = link.strip()

    if link.startswith("@"):
        return link

    if not link.startswith("https://t.me/"):
        return None

    part = link.replace(
        "https://t.me/",
        "",
        1
    )

    part = part.split("/")[0]
    part = part.split("?")[0]

    if part == "":
        return None

    if part.startswith("+"):
        return None

    return "@" + part


# ============== TELEGRAM CHECKS ==============

def is_joined(uid):
    try:
        member = bot.get_chat_member(
            FORCE_CHANNEL,
            uid
        )

        if member.status in [
            "creator",
            "administrator",
            "member"
        ]:
            return True

        if member.status == "restricted":
            return getattr(member, "is_member", False)

        return False

    except:
        return False


def is_bot_admin(chat_id):
    try:
        bot_id = bot.get_me().id

        member = bot.get_chat_member(
            chat_id,
            bot_id
        )

        return member.status in [
            "creator",
            "administrator"
        ]

    except:
        return False


def is_user_member(chat_id, uid):
    try:
        member = bot.get_chat_member(
            chat_id,
            uid
        )

        if member.status in [
            "creator",
            "administrator",
            "member"
        ]:
            return True

        if member.status == "restricted":
            return getattr(member, "is_member", False)

        return False

    except:
        return False


# ============== KEYBOARDS ==============

def main_keyboard(uid):
    mk = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    if get_lang(uid) == "en":
        mk.row(
            types.KeyboardButton("🧾 Order"),
            types.KeyboardButton("🪙 Collect coins")
        )

        mk.row(
            types.KeyboardButton("🎁 Daily coins"),
            types.KeyboardButton("👥 Invite friends")
        )

        mk.row(
            types.KeyboardButton("👤 Account"),
            types.KeyboardButton("📞 Support")
        )

    else:
        mk.row(
            types.KeyboardButton("🧾 ثبت سفارش"),
            types.KeyboardButton("🪙 جمع آوری سکه")
        )

        mk.row(
            types.KeyboardButton("🎁 سکه روزانه"),
            types.KeyboardButton("👥 دعوت دوستان")
        )

        mk.row(
            types.KeyboardButton("👤 حساب"),
            types.KeyboardButton("📞 پشتیبانی")
        )

    return mk


def force_keyboard(uid):
    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(uid, "📢 عضو شدن در کانال", "📢 Join channel"),
        url=FORCE_LINK
    ))

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "✅ عضو شدم، بررسی کن",
            "✅ I joined, check"
        ),
        callback_data="check_join"
    ))

    return mk


def back_keyboard(uid):
    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(uid, "🔙 برگشت", "🔙 Back"),
        callback_data="back"
    ))

    return mk


# ============== MENUS & ACTIONS ==============

def send_welcome(chat_id, uid):
    coins = get_coins(uid)

    text = tx(
        uid,
        "👋 سلام! خوش اومدی\n"
        "💰 موجودی: " + str(coins) + " سکه",

        "👋 Welcome!\n"
        "💰 Balance: " + str(coins) + " coins"
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=main_keyboard(uid)
    )


def send_main(chat_id, uid):
    coins = get_coins(uid)

    text = tx(
        uid,
        "🏠 منوی اصلی\n"
        "💰 موجودی: " + str(coins) + " سکه",

        "🏠 Main menu\n"
        "💰 Balance: " + str(coins) + " coins"
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=main_keyboard(uid)
    )


def send_force(chat_id, uid):
    text = tx(
        uid,
        "⛔ اول باید عضو کانال ما بشی!\n\n" +
        FORCE_LINK +
        "\n\nبعد از عضویت دکمه بررسی را بزن.",

        "⛔ Join our channel first!\n\n" +
        FORCE_LINK +
        "\n\nThen press check."
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=force_keyboard(uid)
    )


# ============== DAILY ==============

def do_daily(chat_id, uid):
    user = get_user(uid)

    coins = user["coins"]
    last_daily = user["last_daily"]

    now = datetime.now()

    if last_daily:
        try:
            old = datetime.fromisoformat(last_daily)

            passed = (
                now - old
            ).total_seconds()

            if passed < 86400:
                remain = int(86400 - passed)

                hours = remain // 3600
                minutes = (
                    remain % 3600
                ) // 60

                text = tx(
                    uid,
                    "⏳ امروز سکه گرفتی!\n"
                    + str(hours) + " ساعت و "
                    + str(minutes) + " دقیقه دیگه بیا.\n"
                    "💰 موجودی: " + str(coins),

                    "⏳ You got daily coins today!\n"
                    "Come back in "
                    + str(hours) + "h "
                    + str(minutes) + "m.\n"
                    "💰 Balance: " + str(coins)
                )

                bot.send_message(
                    chat_id,
                    text,
                    reply_markup=back_keyboard(uid)
                )

                return

        except:
            pass

    new_coins = coins + DAILY_REWARD

    db.execute(
        "UPDATE users SET coins=?, last_daily=? WHERE user_id=?",
        (
            new_coins,
            now.isoformat(),
            uid
        )
    )

    db.commit()

    bot.send_message(
        chat_id,
        tx(
            uid,
            "🎁 " + str(DAILY_REWARD) +
            " سکه روزانه گرفتی!\n"
            "💰 موجودی جدید: " + str(new_coins),

            "🎁 You got " +
            str(DAILY_REWARD) +
            " daily coins!\n"
            "💰 New balance: " + str(new_coins)
        ),
        reply_markup=back_keyboard(uid)
    )


# ============== SUPPORT ==============

def do_support(chat_id, uid):
    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "📞 ارتباط با پشتیبانی",
            "📞 Contact support"
        ),
        url="https://t.me/Behrad_BNB"
    ))

    mk.add(types.InlineKeyboardButton(
        tx(uid, "🔙 برگشت", "🔙 Back"),
        callback_data="back"
    ))

    bot.send_message(
        chat_id,
        tx(
            uid,
            "📞 بخش پشتیبانی\n"
            "پیام بده به:\n" + SUPPORT_ID,

            "📞 Support\n"
            "Contact:\n" + SUPPORT_ID
        ),
        reply_markup=mk
    )


# ============== INVITE ==============

def process_referral(uid):
    if not is_joined(uid):
        return

    user = get_user(uid)

    inviter = user["invited_by"]
    paid = user["referral_paid"]

    if inviter is None:
        return

    if paid == 1:
        return

    if inviter == uid:
        return

    inviter_row = db.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (inviter,)
    ).fetchone()

    if inviter_row is None:
        return

    db.execute("""
    UPDATE users
    SET coins=coins+?,
        invite_count=invite_count+1
    WHERE user_id=?
    """, (
        REF_REWARD,
        inviter
    ))

    db.execute(
        "UPDATE users SET referral_paid=1 WHERE user_id=?",
        (uid,)
    )

    db.commit()

    if notify_on(inviter, "general_notify"):
        try:
            bot.send_message(
                inviter,
                tx(
                    inviter,
                    "🎉 تبریک!\n"
                    "یک نفر با لینک تو اومد و عضو اجباری شد.\n"
                    "💰 " + str(REF_REWARD) +
                    " سکه جایزه گرفتی.",

                    "🎉 Congratulations!\n"
                    "Someone joined with your link.\n"
                    "💰 You got " +
                    str(REF_REWARD) +
                    " coins."
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
        bot.send_message(
            chat_id,
            "Error"
        )

        return

    user = get_user(uid)

    link = (
        "https://t.me/" +
        username +
        "?start=" +
        str(uid)
    )

    share_link = (
        "https://t.me/share/url?url=" +
        quote(link, safe="")
    )

    text = tx(
        uid,
        "👥 دعوت دوستان\n\n"
        "برای هر دوستی که با لینک تو بیاد و عضو اجباری بشه:\n"
        "🎁 " + str(REF_REWARD) +
        " سکه جایزه می‌گیری.\n\n"
        "👤 دعوت موفق: " +
        str(user["invite_count"]) +
        "\n\n🔗 لینک اختصاصی تو:\n" +
        link,

        "👥 Invite friends\n\n"
        "For every friend who joins with your link:\n"
        "🎁 You get " +
        str(REF_REWARD) +
        " coins.\n\n"
        "👤 Successful invites: " +
        str(user["invite_count"]) +
        "\n\n🔗 Your invite link:\n" +
        link
    )

    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "📤 اشتراک گذاری لینک",
            "📤 Share link"
        ),
        url=share_link
    ))

    mk.add(types.InlineKeyboardButton(
        tx(uid, "🔙 برگشت", "🔙 Back"),
        callback_data="back"
    ))

    bot.send_message(
        chat_id,
        text,
        reply_markup=mk
    )


# ============== ACCOUNT ==============

def send_account(chat_id, uid):
    user = get_user(uid)

    orders_count = db.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE user_id=?",
        (uid,)
    ).fetchone()["c"]

    channels_count = db.execute(
        "SELECT COUNT(*) AS c FROM channels WHERE owner_id=?",
        (uid,)
    ).fetchone()["c"]

    collects_count = db.execute(
        "SELECT COUNT(*) AS c FROM collects WHERE user_id=?",
        (uid,)
    ).fetchone()["c"]

    username = user["username"]

    if username:
        username = "@" + username
    else:
        username = "—"

    join_date = str(
        user["joined_at"]
    ).split("T")[0]

    text = tx(
        uid,
        "✨ صفحه حساب کاربری ✨\n"
        "━━━━━━━━━━━━\n\n"
        "🆔 شناسه عددی شما: " +
        str(user["public_id"]) +
        "\n🔗 یوزرنیم شما: " +
        username +
        "\n\n💰 موجودی: " +
        str(user["coins"]) +
        " سکه\n"
        "🧾 مجموع سفارش‌ها: " +
        str(orders_count) +
        "\n📁 کانال‌های ثبت‌شده: " +
        str(channels_count) +
        "\n👥 عضویت‌های جمع‌آوری: " +
        str(collects_count) +
        "\n\n📅 تاریخ عضویت: " +
        join_date,

        "✨ Account ✨\n"
        "━━━━━━━━━━━━\n\n"
        "🆔 Account ID: " +
        str(user["public_id"]) +
        "\n🔗 Username: " +
        username +
        "\n\n💰 Balance: " +
        str(user["coins"]) +
        "\n🧾 Orders: " +
        str(orders_count) +
        "\n📁 Channels: " +
        str(channels_count) +
        "\n👥 Collections: " +
        str(collects_count) +
        "\n\n📅 Join date: " +
        join_date
    )

    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(uid, "⚙️ تنظیمات", "⚙️ Settings"),
        callback_data="settings"
    ))

    bot.send_message(
        chat_id,
        text,
        reply_markup=mk
    )


# ============== SETTINGS ==============

def send_settings(chat_id, uid):
    mk = types.InlineKeyboardMarkup()

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "🔔 تنظیمات اعلان‌ها",
            "🔔 Notifications"
        ),
        callback_data="notifications"
    ))

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "🌐 تغییر زبان",
            "🌐 Change language"
        ),
        callback_data="languages"
    ))

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "🏠 منوی اصلی",
            "🏠 Main menu"
        ),
        callback_data="back"
    ))

    bot.send_message(
        chat_id,
        tx(
            uid,
            "⚙️ تنظیمات\n\n"
            "حساب کاربری خود را مدیریت کنید.",

            "⚙️ Settings\n\n"
            "Manage your account."
        ),
        reply_markup=mk
    )


def notify_status(uid, column):
    if notify_on(uid, column):
        return tx(uid, "فعال ✅", "Active ✅")

    return tx(uid, "غیرفعال ❌", "Inactive ❌")


def send_notifications(chat_id, uid):
    mk = types.InlineKeyboardMarkup()

    label1 = tx(
        uid,
        "📈 تکمیل سفارش: ",
        "📈 Order completion: "
    )

    label1 += notify_status(uid, "order_notify")

    mk.add(types.InlineKeyboardButton(
        label1,
        callback_data="notify_order"
    ))

    label2 = tx(
        uid,
        "📢 پیام همگانی: ",
        "📢 General messages: "
    )

    label2 += notify_status(uid, "general_notify")

    mk.add(types.InlineKeyboardButton(
        label2,
        callback_data="notify_general"
    ))

    label3 = tx(
        uid,
        "⚠️ هشدارهای سیستمی: ",
        "⚠️ System warnings: "
    )

    label3 += notify_status(uid, "system_notify")

    mk.add(types.InlineKeyboardButton(
        label3,
        callback_data="notify_system"
    ))

    label4 = tx(
        uid,
        "🏆 رقابت ماهانه: ",
        "🏆 Monthly contest: "
    )

    label4 += notify_status(uid, "contest_notify")

    mk.add(types.InlineKeyboardButton(
        label4,
        callback_data="notify_contest"
    ))

    mk.add(types.InlineKeyboardButton(
        tx(
            uid,
            "🔙 بازگشت به تنظیمات",
            "🔙 Back to settings"
        ),
        callback_data="settings"
    ))

    bot.send_message(
        chat_id,
        tx(
            uid,
            "🔔 تنظیمات اعلان‌ها\n\n"
            "مشخص کنید کدام اعلان‌ها را دریافت کنید.",

            "🔔 Notification settings\n\n"
            "Choose notifications."
        ),
        reply_markup=mk
    )


def send_languages(chat_id, uid):
    mk = types.InlineKeyboardMarkup()

    current = get_lang(uid)

    fa_mark = " ✅" if current == "fa" else ""
    en_mark = " ✅" if current == "en" else ""

    mk.add(types.InlineKeyboardButton(
        "🇮🇷 فارسی" + fa_mark,
        callback_data="set_lang_fa"
    ))

    mk.add(types.InlineKeyboardButton(
        "🇬🇧 English" + en_mark,
        callback_data="set_lang_en"
    ))

    mk.add(types.InlineKeyboardButton(
        tx(uid, "🔙 بازگشت به تنظیمات", "🔙 Back to settings"),
        callback_data="settings"
    ))

    bot.send_message(
        chat_id,
        tx(
            uid,
            "🌐 زبان خود را انتخاب کنید:",
            "🌐 Choose your language:"
        ),
        reply_markup=mk
    )


# ============== COLLECT COINS & ORDERS ==============

def do_collect(chat_id, uid):
    row = db.execute("""
        SELECT c.* FROM channels c
        WHERE c.owner_id != ?
        AND c.id NOT IN (SELECT channel_db_id FROM collects WHERE user_id=?)
        LIMIT 1
    """, (uid, uid)).fetchone()

    if not row:
        bot.send_message(
            chat_id,
            tx(uid, "❌ در حال حاضر کانالی برای کسب سکه وجود ندارد.", "❌ No channels available right now."),
            reply_markup=back_keyboard(uid)
        )
        return

    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(tx(uid, "📢 ورود به کانال", "📢 Join channel"), url=row["link"]))
    mk.add(types.InlineKeyboardButton(tx(uid, "✅ دریافت سکه", "✅ Verify & Get Coin"), callback_data=f"get_coin_{row['id']}"))
    mk.add(types.InlineKeyboardButton(tx(uid, "🔙 برگشت", "🔙 Back"), callback_data="back"))

    bot.send_message(
        chat_id,
        tx(
            uid,
            f"📢 در کانال زیر عضو شو و پس از عضویت روی دکمه دریافت سکه بزن:\n\n{row['link']}",
            f"📢 Join the channel and click verify:\n\n{row['link']}"
        ),
        reply_markup=mk
    )


def do_order(chat_id, uid):
    states[uid] = "waiting_channel"
    text = tx(
        uid,
        "🔗 **افزودن کانال/گروه**\n\n"
        "⚠️ ربات باید ادمین کانال/گروه باشد!\n\n"
        "✅ @my_channel یا https://t.me/my_channel\n"
        "❌ لینک خصوصی (t.me/+...) مجاز نیست\n\n"
        "لطفاً لینک یا آیدی کانال خود را ارسال کنید:",
        
        "🔗 **Add Channel/Group**\n\n"
        "⚠️ Bot must be admin!\n\n"
        "✅ @my_channel or https://t.me/my_channel\n"
        "❌ Private links not allowed\n\n"
        "Send your channel link or username:"
    )
    bot.send_message(chat_id, text, reply_markup=back_keyboard(uid), parse_mode="Markdown")


# ============== CALLBACK & MESSAGE HANDLERS ==============

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    ensure_user(uid, call.from_user)

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if data == "back" or data == "settings":
        states.pop(uid, None)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        if data == "settings":
            send_settings(chat_id, uid)
        else:
            send_main(chat_id, uid)

    elif data == "languages":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        send_languages(chat_id, uid)

    elif data == "set_lang_fa":
        db.execute("UPDATE users SET language='fa' WHERE user_id=?", (uid,))
        db.commit()
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        bot.send_message(chat_id, "✅ زبان به فارسی تغییر کرد.", reply_markup=main_keyboard(uid))

    elif data == "set_lang_en":
        db.execute("UPDATE users SET language='en' WHERE user_id=?", (uid,))
        db.commit()
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        bot.send_message(chat_id, "✅ Language changed to English.", reply_markup=main_keyboard(uid))

    elif data == "notifications":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        send_notifications(chat_id, uid)

    elif data.startswith("notify_"):
        col_map = {
            "notify_order": "order_notify",
            "notify_general": "general_notify",
            "notify_system": "system_notify",
            "notify_contest": "contest_notify"
        }
        col = col_map.get(data)
        if col:
            current = get_user(uid)[col]
            new_val = 0 if current == 1 else 1
            db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (new_val, uid))
            db.commit()
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            send_notifications(chat_id, uid)

    elif data == "check_join":
        if is_joined(uid):
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            process_referral(uid)
            send_welcome(chat_id, uid)
        else:
            bot.answer_callback_query(call.id, tx(uid, "⛔ شما هنوز عضو کانال نشده‌اید!", "⛔ You haven't joined yet!"), show_alert=True)

    elif data.startswith("get_coin_"):
        try:
            channel_db_id = int(data.split("_")[2])
            channel = db.execute("SELECT * FROM channels WHERE id=?", (channel_db_id,)).fetchone()
            
            if not channel:
                bot.answer_callback_query(call.id, "❌ کانال یافت نشد.", show_alert=True)
                return

            if is_user_member(channel["chat_id"], uid):
                already = db.execute("SELECT * FROM collects WHERE user_id=? AND channel_db_id=?", (uid, channel_db_id)).fetchone()
                if already:
                    bot.answer_callback_query(call.id, tx(uid, "⚠️ شما قبلاً سکه این کانال را دریافت کرده‌اید!", "⚠️ You already collected from this channel!"), show_alert=True)
                    return

                db.execute("INSERT INTO collects(user_id, channel_db_id) VALUES(?, ?)", (uid, channel_db_id))
                db.execute("UPDATE users SET coins = coins + 1 WHERE user_id=?", (uid,))
                db.commit()

                bot.answer_callback_query(call.id, tx(uid, "🎉 ۱ سکه به حساب شما اضافه شد!", "🎉 +1 coin added!"), show_alert=True)
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except:
                    pass
                do_collect(chat_id, uid)
            else:
                bot.answer_callback_query(call.id, tx(uid, "⛔ شما هنوز در کانال عضو نشده‌اید!", "⛔ You haven't joined the channel yet!"), show_alert=True)
        except Exception as e:
            print(e)
            bot.answer_callback_query(call.id, "❌ خطا در بررسی عضویت.", show_alert=True)


@bot.message_handler(commands=['start'])
def start_command(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    args = message.text.split()
    states.pop(uid, None)

    is_new = ensure_user(uid, message.from_user)

    if is_new and len(args) > 1:
        try:
            inviter_id = int(args[1])
            if inviter_id != uid:
                db.execute("UPDATE users SET invited_by=? WHERE user_id=?", (inviter_id, uid))
                db.commit()
        except:
            pass

    if not is_joined(uid):
        send_force(chat_id, uid)
        return

    process_referral(uid)
    send_welcome(chat_id, uid)


@bot.message_handler(func=lambda message: True)
def text_handler(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()

    ensure_user(uid, message.from_user)

    if not is_joined(uid):
        send_force(chat_id, uid)
        return

    current_state = states.get(uid)
    if current_state == "waiting_channel":
        username = get_channel_username(text)
        if not username:
            bot.send_message(chat_id, tx(
                uid,
                "❌ لینک یا آیدی وارد شده نامعتبر است.\nلطفاً طبق نمونه ارسال کنید (مثال: @my_channel):",
                "❌ Invalid link or username. Try again:"
            ))
            return
        
        if not is_bot_admin(username):
            bot.send_message(chat_id, tx(
                uid,
                "❌ **خطا:** ربات در کانال شما ادمین نیست!\n"
                "لطفاً ابتدا ربات را در کانال ادمین کنید و سپس دوباره لینک را بفرستید.",
                "❌ Error: Bot is not admin in the channel!"
            ), parse_mode="Markdown")
            return

        states[uid] = f"waiting_count:{username}"
        bot.send_message(
            chat_id,
            tx(
                uid,
                f"✅ کانال تایید شد: `{username}`\n\n"
                f"📊 تعداد ممبرهای درخواستی خود را به عدد وارد کنید:\n"
                f"(هر ۱ ممبر = ۱ سکه 🪙 | حداکثر {MAX_ORDER} ممبر)",
                f"✅ Channel verified: `{username}`\n\n"
                f"📊 Enter member count:"
            ),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )
        return

    elif current_state and current_state.startswith("waiting_count:"):
        username = current_state.split(":")[1]
        count = parse_number(text)
        
        if not count or count <= 0:
            bot.send_message(chat_id, tx(
                uid,
                "❌ لطفاً تعداد ممبرها را به صورت **عدد** معتبر وارد کنید:",
                "❌ Please enter a valid number:"
            ), parse_mode="Markdown")
            return

        if count > MAX_ORDER:
            bot.send_message(chat_id, tx(
                uid,
                f"❌ حداکثر تعداد سفارش در هر بار {MAX_ORDER} ممبر است.",
                f"❌ Max order limit is {MAX_ORDER}."
            ))
            return

        coins = get_coins(uid)
        if coins < count:
            bot.send_message(
                chat_id,
                tx(
                    uid,
                    f"❌ موجودی شما کافی نیست!\n\n"
                    f"💰 موجودی فعلی: {coins} سکه\n"
                    f"🪙 سکه مورد نیاز: {count} سکه",
                    f"❌ Insufficient balance!"
                ),
                reply_markup=main_keyboard(uid)
            )
            states.pop(uid, None)
            return

        # کسر سکه
        db.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (count, uid))
        
        # ثبت کانال
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO channels(owner_id, chat_id, title, link) VALUES(?, ?, ?, ?)",
            (uid, username, username, f"https://t.me/{username.replace('@','')}")
        )
        channel_db_id = cursor.lastrowid

        # ثبت سفارش و دریافت شناسه سفارش (ID)
        cursor.execute(
            "INSERT INTO orders(user_id, channel_db_id, need_count, done_count, date) VALUES(?, ?, ?, 0, ?)",
            (uid, channel_db_id, count, datetime.now().isoformat())
        )
        order_id = cursor.lastrowid
        db.commit()
        states.pop(uid, None)

        success_text = tx(
            uid,
            f"✅ **سفارش شما با موفقیت ثبت شد!**\n\n"
            f"🆔 شماره سفارش: `#{order_id}`\n"
            f"📢 کانال: `{username}`\n"
            f"📦 تعداد درخواستی: {count} ممبر\n"
            f"🪙 سکه کسر شده: {count} سکه\n\n"
            f"سپاس از اعتماد شما 🙏",
            
            f"✅ **Order successfully placed!**\n\n"
            f"🆔 Order ID: `#{order_id}`\n"
            f"📢 Channel: `{username}`\n"
            f"📦 Count: {count}\n"
            f"🪙 Coins deducted: {count}"
        )

        bot.send_message(chat_id, success_text, reply_markup=main_keyboard(uid), parse_mode="Markdown")
        return

    # مدیریت دکمه‌های منوی اصلی
    if text in ["🏠 منوی اصلی", "🏠 Main menu"]:
        states.pop(uid, None)
        send_main(chat_id, uid)
    elif text in ["🪙 جمع آوری سکه", "🪙 Collect coins"]:
        do_collect(chat_id, uid)
    elif text in ["🧾 ثبت سفارش", "🧾 Order"]:
        do_order(chat_id, uid)
    elif text in ["🎁 سکه روزانه", "🎁 Daily coins"]:
        do_daily(chat_id, uid)
    elif text in ["👥 دعوت دوستان", "👥 Invite friends"]:
        do_invite(chat_id, uid)
    elif text in ["👤 حساب", "👤 Account"]:
        send_account(chat_id, uid)
    elif text in ["📞 پشتیبانی", "📞 Support"]:
        do_support(chat_id, uid)
    else:
        send_main(chat_id, uid)


if __name__ == "__main__":
    print("Bot is running...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)
      
