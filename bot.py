import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime

# Render-এর Environment থেকে টোকেন নেবে, না পেলে আপনার দেওয়া টোকেনটি ডিফল্ট হিসেবে কাজ করবে
BOT_TOKEN = os.getenv("BOT_TOKEN", "8008124642:AAEzqg4R_eWfSnjz6R-0ShjNznw44ZLnkWA")
DATA_FILE = "timers.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def load_timers():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_timers(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Save Error: {e}")

user_timers = load_timers()

def get_main_keyboard(user_id_str):
    if user_id_str in user_timers:
        keyboard = [[InlineKeyboardButton("🔙 Back (ফিরে এসেছি)", callback_data="back")]]
    else:
        keyboard = [[InlineKeyboardButton("🚬 Smoke / Break (বাইরে যাচ্ছি)", callback_data="punch")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_str = str(update.effective_user.id)
    reply_markup = get_main_keyboard(user_id_str)
    await update.message.reply_text(
        "👋 **Punch Time Bot-এ স্বাগতম!**\n\nনিচের বাটনে চাপ দিয়ে আপনার ব্রেক শুরু বা শেষ করুন:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id_str = str(query.from_user.id)
    user_name = query.from_user.first_name
    now = datetime.now()

    if query.data == "punch":
        if user_id_str in user_timers:
            await query.edit_message_text(
                text=f"⚠️ **{user_name}**, আপনি তো অলরেডি ব্রেকে আছেন!",
                reply_markup=get_main_keyboard(user_id_str),
                parse_mode="Markdown"
            )
            return

        user_timers[user_id_str] = now.isoformat()
        save_timers(user_timers)
        start_time_str = now.strftime("%I:%M %p")
        
        await query.edit_message_text(
            text=f"🚬 **{user_name}** ব্রেকে গেছেন!\n⏰ **শুরুর সময়:** {start_time_str}\n\nফিরে এসে নিচের বাটনে চাপ দিন:",
            reply_markup=get_main_keyboard(user_id_str),
            parse_mode="Markdown"
        )

    elif query.data == "back":
        if user_id_str in user_timers:
            start_iso = user_timers.pop(user_id_str)
            save_timers(user_timers)
            
            start_time = datetime.fromisoformat(start_iso)
            duration = now - start_time
            
            total_seconds = int(duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            
            await query.edit_message_text(
                text=f"✅ **{user_name}** ফিরে এসেছেন!\n⏱️ **মোট সময় লেগেছে:** {minutes} মিনিট {seconds} সেকেন্ড।\n\nআবার ব্রেকে যেতে চাইলে বাটনে চাপ দিন:",
                reply_markup=get_main_keyboard(user_id_str),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                text="⚠️ আপনি তো ব্রেকে যাননি! ব্রেকে যেতে নিচের বাটনে চাপ দিন:",
                reply_markup=get_main_keyboard(user_id_str),
                parse_mode="Markdown"
            )

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()
