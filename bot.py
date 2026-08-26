import logging
import sqlite3
from datetime import datetime, time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    TypeHandler
)

# ---------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------
BOT_TOKEN = "8008124642:AAEzqg4R_eWfSnjz6R-0ShjNznw44ZLnkWA"  # Your API Token

ACTIVE_START = time(9, 0)   # 9:00 AM
ACTIVE_END = time(21, 0)   # 9:00 PM
OFFICIAL_START = time(9, 45)  # 9:45 AM
GRACE_END = time(9, 50)      # 9:50 AM

BREAK_LIMITS = {
    'eat': {'max_count': 2, 'duration_min': 20, 'name': '🍚 Eat'},
    'toilet': {'max_count': 8, 'duration_min': 15, 'name': '🚽 Toilet'},
    'smoke': {'max_count': 8, 'duration_min': 10, 'name': '🚬 Smoke'}
}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ---------------------------------------------------------
# Database Setup
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect('punch_bot.db')
    cursor = conn.cursor()
    
    # Active Sessions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            start_time TEXT,
            late_minutes INTEGER,
            status TEXT,
            current_break TEXT,
            break_start_time TEXT
        )
    ''')
    
    # Daily Break Usage Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS break_usage (
            user_id INTEGER,
            date TEXT,
            eat_count INTEGER DEFAULT 0,
            toilet_count INTEGER DEFAULT 0,
            smoke_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    ''')
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Middleware: Active Hours Check (9 AM - 9 PM)
# ---------------------------------------------------------
async def active_hours_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    now_time = datetime.now().time()
    if not (ACTIVE_START <= now_time <= ACTIVE_END):
        await update.message.reply_text("⛔ **Bot Inactive!** বট কেবল সকাল ৯:০০ টা থেকে রাত ৯:০০ টা পর্যন্ত কার্যকর থাকে।", parse_mode='Markdown')
        context.drop_child_handlers()

# ---------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------

# 🟢 Start Work (/start_work বা /in)
async def start_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    now_time = now.time()

    conn = sqlite3.connect('punch_bot.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM sessions WHERE user_id = ?", (user.id,))
    session = cursor.fetchone()

    if session:
        await update.message.reply_text(f"⚠️ **{user.first_name}**, তুমি ইতোমধ্যে Shift চালু করেছ!")
        conn.close()
        return

    # Late Calculation Logic
    late_minutes = 0
    if now_time > GRACE_END:
        official_datetime = datetime.combine(now.date(), OFFICIAL_START)
        late_minutes = int((now - official_datetime).total_seconds() // 60)

    cursor.execute('''
        INSERT INTO sessions (user_id, user_name, start_time, late_minutes, status)
        VALUES (?, ?, ?, ?, 'WORKING')
    ''', (user.id, user.first_name, now.strftime("%Y-%m-%d %H:%M:%S"), late_minutes))

    cursor.execute('''
        INSERT OR IGNORE INTO break_usage (user_id, date, eat_count, toilet_count, smoke_count)
        VALUES (?, ?, 0, 0, 0)
    ''', (user.id, today_str))

    conn.commit()
    conn.close()

    msg = f"🟢 **Start Work Recorded!**\n👤 User: {user.first_name}\n⏰ Time: {now.strftime('%I:%M %p')}\n"
    if late_minutes > 0:
        msg += f"⚠️ **Status:** Late ({late_minutes} মিনিট)"
    else:
        msg += "✅ **Status:** On Time"

    await update.message.reply_text(msg, parse_mode='Markdown')


# 🍚 /eat, 🚽 /toilet, 🚬 /smoke
async def start_break(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    command = update.message.text.split()[0].replace('/', '').lower()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if command not in BREAK_LIMITS:
        return

    break_info = BREAK_LIMITS[command]
    break_name = break_info['name']
    max_count = break_info['max_count']

    conn = sqlite3.connect('punch_bot.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status, current_break FROM sessions WHERE user_id = ?", (user.id,))
    session = cursor.fetchone()

    if not session:
        await update.message.reply_text("❌ আগে `/start_work` বা `/in` দিয়ে শিফট শুরু করো!", parse_mode='Markdown')
        conn.close()
        return

    if session[0] == 'ON_BREAK':
        await update.message.reply_text(f"⚠️ তুমি বর্তমানে **{session[1]}** এ আছ। সিটে ফিরতে `/back` চাপো।", parse_mode='Markdown')
        conn.close()
        return

    # Check daily usage count
    column_name = f"{command}_count"
    cursor.execute(f"SELECT {column_name} FROM break_usage WHERE user_id = ? AND date = ?", (user.id, today_str))
    usage_res = cursor.fetchone()
    current_usage = usage_res[0] if usage_res else 0

    if current_usage >= max_count:
        await update.message.reply_text(f"🚫 **Limit Reached!** আজকের জন্য {break_name} ব্রেকের সীমাবদ্ধতা ({max_count} বার) শেষ হয়ে গেছে।", parse_mode='Markdown')
        conn.close()
        return

    # Update state to ON_BREAK
    new_count = current_usage + 1
    cursor.execute(f"UPDATE break_usage SET {column_name} = ? WHERE user_id = ? AND date = ?", (new_count, user.id, today_str))
    cursor.execute("UPDATE sessions SET status = 'ON_BREAK', current_break = ?, break_start_time = ? WHERE user_id = ?",
                   (break_name, now.strftime("%Y-%m-%d %H:%M:%S"), user.id))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"{break_name} **Started!**\n👤 User: {user.first_name}\n⏱️ Max Time: {break_info['duration_min']} মিনিট\n📊 আজকের ব্যবহার: {new_count}/{max_count}",
        parse_mode='Markdown'
    )


# 🪑 Back to Seat (/back)
async def back_to_seat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    conn = sqlite3.connect('punch_bot.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status, current_break, break_start_time FROM sessions WHERE user_id = ?", (user.id,))
    session = cursor.fetchone()

    if not session or session[0] != 'ON_BREAK':
        await update.message.reply_text("⚠️ তুমি বর্তমানে কোনো ব্রেক-এ নেই!", parse_mode='Markdown')
        conn.close()
        return

    break_name = session[1]
    break_start = datetime.strptime(session[2], "%Y-%m-%d %H:%M:%S")
    duration_min = int((now - break_start).total_seconds() // 60)

    cursor.execute("UPDATE sessions SET status = 'WORKING', current_break = NULL, break_start_time = NULL WHERE user_id = ?", (user.id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🪑 **Back to Seat!**\n👤 User: {user.first_name}\n🔹 Break: {break_name}\n⏱️ মোট সময় লেগেছে: {duration_min} মিনিট",
        parse_mode='Markdown'
    )


# 🔴 Off Work (/off_work বা /out)
async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    conn = sqlite3.connect('punch_bot.db')
    cursor = conn.cursor()

    cursor.execute("SELECT start_time, late_minutes FROM sessions WHERE user_id = ?", (user.id,))
    session = cursor.fetchone()

    if not session:
        await update.message.reply_text("⚠️ তুমি আজকে কোনো শিফট চালু করোনি!", parse_mode='Markdown')
        conn.close()
        return

    start_time = datetime.strptime(session[0], "%Y-%m-%d %H:%M:%S")
    total_hours = round((now - start_time).total_seconds() / 3600, 2)
    late_min = session[1]

    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user.id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🔴 **Off Work Recorded!**\n👤 User: {user.first_name}\n⏰ Time: {now.strftime('%I:%M %p')}\n⏱️ মোট কাজ: {total_hours} ঘণ্টা\n⚠️ আজকের লেট: {late_min} মিনিট",
        parse_mode='Markdown'
    )


# ---------------------------------------------------------
# App Main Execution
# ---------------------------------------------------------
if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Active Hours Listener (Global Middleware)
    app.add_handler(TypeHandler(Update, active_hours_middleware), group=-1)

    # Command Handlers Setup
    app.add_handler(CommandHandler(["start_work", "in"], start_work))
    app.add_handler(CommandHandler("eat", start_break))
    app.add_handler(CommandHandler("toilet", start_break))
    app.add_handler(CommandHandler("smoke", start_break))
    app.add_handler(CommandHandler("back", back_to_seat))
    app.add_handler(CommandHandler(["off_work", "out"], off_work))

    print("Bot is successfully running with configured rules...")
    app.run_polling()
