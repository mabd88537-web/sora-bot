import os
import logging
import psycopg2
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
CAIRO_TZ = pytz.timezone('Africa/Cairo')

TEAM1, TEAM2, TIME, LINK = range(4)

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL,
            match_time TIMESTAMP NOT NULL,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 مباريات اليوم", callback_data="today_matches")],
        [InlineKeyboardButton("📋 كل المباريات", callback_data="all_matches")]
    ]
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔐 لوحة الأدمن", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚽ أهلا بيك في *الكورة في قرية الصورة*\nتابع كل مباريات القرية لحظة بلحظة", reply_markup=reply_markup, parse_mode='Markdown')

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE, today_only=False):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    cur = conn.cursor()
    if today_only:
        cur.execute("SELECT * FROM matches WHERE DATE(match_time) = CURRENT_DATE ORDER BY match_time")
        title = "📅 *مباريات اليوم - قرية الصورة*"
    else:
        cur.execute("SELECT * FROM matches WHERE match_time >= NOW() ORDER BY match_time")
        title = "📋 *كل المباريات القادمة*"
    matches = cur.fetchall()
    cur.close()
    conn.close()
    if not matches:
        await query.edit_message_text("❌ مفيش مباريات حالياً في القرية")
        return
    text = f"{title}\n\n"
    for m in matches:
        match_id, team1, team2, match_time, link, _ = m
        time_str = match_time.astimezone(CAIRO_TZ).strftime('%I:%M %p - %d/%m')
        text += f"🏟️ *{team1}* vs *{team2}*\n⏰ {time_str}\n"
        if link: text += f"📺 [مشاهدة البث]({link})\n"
        if update.effective_user.id == ADMIN_ID: text += f"🗑️ /del_{match_id}\n"
        text += "━━━━━━━━━━━━━━\n"
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_home")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown', disable_web_page_preview=True)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id!= ADMIN_ID:
        await query.answer("❌ مش مسموحلك", show_alert=True)
        return
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مباراة", callback_data="add_match")],
        [InlineKeyboardButton("📋 عرض المباريات", callback_data="all_matches")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")]
    ]
    await query.edit_message_text("🔐 **لوحة تحكم الكورة في قرية الصورة**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ابعت اسم الفريق الأول:\n\n/cancel للإلغاء")
    return TEAM1

async def get_team1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team1'] = update.message.text
    await update.message.reply_text("تمام ✅\nابعت اسم الفريق الثاني:")
    return TEAM2

async def get_team2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team2'] = update.message.text
    await update.message.reply_text("ابعت معاد المباراة\nمثال: 2026-05-28 21:00\n\nالوقت بتوقيت مصر")
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        match_time = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        match_time = CAIRO_TZ.localize(match_time)
        context.user_data['time'] = match_time
        await update.message.reply_text("آخر حاجة: ابعت رابط البث أو اكتب تخطي")
        return LINK
    except:
        await update.message.reply_text("❌ صيغة الوقت غلط\nمثال صحيح: 2026-05-28 21:00")
        return TIME

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = None if update.message.text.lower() == 'تخطي' else update.message.text
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO matches (team1, team2, match_time, link) VALUES (%s, %s, %s, %s)",
                (context.user_data['team1'], context.user_data['team2'], context.user_data['time'], link))
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text("✅ تم إضافة المباراة بنجاح")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

async def delete_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    match_id = int(update.message.text.split('_')[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM matches WHERE id = %s", (match_id,))
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text(f"✅ تم حذف المباراة رقم {match_id}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM matches WHERE match_time >= NOW()")
    upcoming = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM matches")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    text = f"📊 *إحصائيات الكورة في قرية الصورة*\n\n🔥 المباريات القادمة: {upcoming}\n📦 إجمالي المباريات: {total}"
    await query.edit_message_text(text, parse_mode='Markdown')

async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await start(query, context)

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_match_start, pattern='^add_match$')],
        states={
            TEAM1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_team1)],
            TEAM2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_team2)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex(r'^/del_\d+$'), delete_match))
    app.add_handler(CallbackQueryHandler(show_matches, pattern='^today_matches$'))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_matches(u, c, False), pattern='^all_matches$'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    app.add_handler(CallbackQueryHandler(stats, pattern='^stats$'))
    app.add_handler(CallbackQueryHandler(back_home, pattern='^back_home$'))
    print("الكورة في قرية الصورة شغال...")
    app.run_polling()

if __name__ == '__main__':
    main()
