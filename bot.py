import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # আপনার বটের টোকেন বসান

# স্মোকিং টাইমার ট্র্যাকিং ডিকশনারি
user_timers = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# বাটন লেআউট তৈরির ফাংশন
def get_main_keyboard(user_id):
    if user_id in user_timers:
        # ইউজার যদি অলরেডি বাইরে থাকে, তবে 'Back' বাটন দেখাবে
        keyboard = [
            [InlineKeyboardButton("🔙 Back (ফিরে এসেছি)", callback_data="back")]
        ]
    else:
        # ইউজার যদি ভেতরে থাকে, তবে 'Punch / Smoke' বাটন দেখাবে
        keyboard = [
            [InlineKeyboardButton("🚬 Punch / Break (বাইরে যাচ্ছি)", callback_data="punch")]
        ]
    return InlineKeyboardMarkup(keyboard)

# /start দিলে প্রথম বাটন শো করবে
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reply_markup = get_main_keyboard(user_id)
    await update.message.reply_text(
        "👋 **Punch Time Bot-এ স্বাগতম!**\n\nনিচের বাটনে চাপ দিয়ে আপনার ব্রেক টাইম ট্র্যাক করুন:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# বাটনে ক্লিক করলে যা ঘটবে
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    now = datetime.now()

    if query.data == "punch":
        # সময় সেভ রাখা
        user_timers[user_id] = now
        start_time_str = now.strftime("%I:%M %p")
        
        reply_markup = get_main_keyboard(user_id)
        await query.edit_message_text(
            text=f"🚬 **{user_name}** ব্রেকে গেছেন!\n⏰ **শুরূর সময়:** {start_time_str}\n\nফিরে এসে নিচের বাটনে চাপ দিন:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "back":
        if user_id in user_timers:
            start_time = user_timers.pop(user_id)
            duration = now - start_time
            
            total_seconds = int(duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            
            reply_markup = get_main_keyboard(user_id)
            await query.edit_message_text(
                text=f"✅ **{user_name}** ফিরে এসেছেন!\n⏱️ **মোট সময় লেগেছে:** {minutes} মিনিট {seconds} সেকেন্ড।\n\nআবার ব্রেক নিতে চাইলে নিচের বাটনে চাপ দিন:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            reply_markup = get_main_keyboard(user_id)
            await query.edit_message_text(
                text="⚠️ আপনি তো ব্রেকে যাননি! ব্রেক শুরু করতে নিচের বাটনে চাপ দিন:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    
    app.run_polling()
