import os
import threading
import logging
from datetime import datetime
import pytz
import psycopg2
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
CAIRO_TZ = pytz.timezone('Africa/Cairo')

# ========== قاعدة البيانات ==========
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
            stadium TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# ========== الموقع Flask ==========
app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>الكورة في قرية الصورة</title>
    <style>
        body { font-family: 'Cairo', sans-serif; background: #0f172a; color: #fff; margin: 0; padding: 20px; }
       .header { text-align: center; background: linear-gradient(135deg, #16a34a, #15803d); padding: 30px; border-radius: 15px; margin-bottom: 30px; }
        h1 { margin: 0; font-size: 32px; }
       .match { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 15px; border-right: 4px solid #16a34a; }
       .teams { font-size: 24px; font-weight: bold; margin-bottom: 10px; }
       .time { color: #94a3b8; margin-bottom: 10px; }
       .link { display: inline-block; background: #dc2626; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; margin-top: 10px; }
       .stadium { color: #fbbf24; }
       .no-matches { text-align: center; padding: 40px; color: #64748b; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚽ الكورة في قرية الصورة</h1>
        <p>تابع كل مباريات القرية لحظة بلحظة</p>
    </div>
    {% if matches %}
        {% for m in matches %}
        <div class="match">
            <div class="teams">{{ m[1] }} VS {{ m[2] }}</div>
            <div class="time">⏰ {{ m[3] }}</div>
            {% if m[5] %}<div class="stadium">🏟️ {{ m[5] }}</div>{% endif %}
            {% if m[4] %}<a href="{{ m[4] }}" class="link" target="_blank">📺 مشاهدة البث</a>{% endif %}
        </div>
        {% endfor %}
    {% else %}
        <div class="no-matches">❌ مفيش مباريات حالياً</div>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches WHERE match_time >= NOW() ORDER BY match_time")
    matches = cur.fetchall()
    # حول الوقت لصيغة مقروءة
    matches_list = []
    for m in matches:
        time_str = m[3].astimezone(CAIRO_TZ).strftime('%I:%M %p - %d/%m/%Y')
        matches_list.append((m[0], m[1], m[2], time_str, m[4], m[5]))
    cur.close()
    conn.close()
    return render_template_string(HTML, matches=matches_list)

# ========== بوت التليجرام ==========
TEAM1, TEAM2, TIME, LINK, STADIUM = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("🔐 لوحة تحكم الأدمن", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚽ *الكورة في قرية الصورة*\n\nانت الأدمن يا معلم 💚", reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text("⚽ *الكورة في قرية الصورة*\n\nتابع المباريات من الموقع الرسمي 👇", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id!= ADMIN_ID:
        await query.answer("❌ مش مسموحلك", show_alert=True)
        return
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مباراة للموقع", callback_data="add_match")],
        [InlineKeyboardButton("🗑️ حذف مباراة", callback_data="delete_match")],
        [InlineKeyboardButton("📋 عرض كل المباريات", callback_data="list_matches")],
        [InlineKeyboardButton("🌐 رابط الموقع", callback_data="site_link")]
    ]
    await query.edit_message_text("🔐 **لوحة التحكم الكاملة**\n\nأي حاجة تضيفها هنا هتظهر في الموقع فوراً", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("1️⃣ ابعت اسم الفريق الأول:\n\n/cancel للإلغاء")
    return TEAM1

async def get_team1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team1'] = update.message.text
    await update.message.reply_text("2️⃣ ابعت اسم الفريق الثاني:")
    return TEAM2

async def get_team2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team2'] = update.message.text
    await update.message.reply_text("3️⃣ ابعت معاد المباراة\nمثال: 2026-05-28 21:00")
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        match_time = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        context.user_data['time'] = CAIRO_TZ.localize(match_time)
        await update.message.reply_text("4️⃣ ابعت رابط البث أو اكتب تخطي:")
        return LINK
    except:
        await update.message.reply_text("❌ صيغة غلط\nمثال: 2026-05-28 21:00")
        return TIME

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link'] = None if update.message.text.lower() == 'تخطي' else update.message.text
    await update.message.reply_text("5️⃣ اسم الملعب أو اكتب تخطي:")
    return STADIUM

async def get_stadium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stadium = None if update.message.text.lower() == 'تخطي' else update.message.text
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO matches (team1, team2, match_time, link, stadium) VALUES (%s, %s, %s, %s, %s)",
                (context.user_data['team1'], context.user_data['team2'], context.user_data['time'], context.user_data['link'], stadium))
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text(f"✅ تم إضافة المباراة للموقع بنجاح\n\n{context.user_data['team1']} VS {context.user_data['team2']}\n\nأي حد هيفتح الموقع دلوقتي هيلاقيها")
    context.user_data.clear()
    return ConversationHandler.END

async def list_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches WHERE match_time >= NOW() ORDER BY match_time")
    matches = cur.fetchall()
    cur.close()
    conn.close()
    if not matches:
        await query.edit_message_text("❌ مفيش مباريات")
        return
    text = "📋 *المباريات الحالية في الموقع:*\n\n"
    for m in matches:
        time_str = m[3].astimezone(CAIRO_TZ).strftime('%d/%m %I:%M%p')
        text += f"🆔 {m[0]} | {m[1]} vs {m[2]} | {time_str}\n/del_{m[0]}\n\n"
    await query.edit_message_text(text, parse_mode='Markdown')

async def delete_match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("ابعت /del_ وبعدها رقم المباراة\nمثال: /del_5\n\nهتلاقي الأرقام في 'عرض كل المباريات'")

async def delete_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    match_id = int(update.message.text.split('_')[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM matches WHERE id = %s", (match_id,))
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text(f"✅ تم حذف المباراة {match_id} من الموقع")

async def site_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "اللينك لسه متعملش")
    await query.answer()
    await query.edit_message_text(f"🌐 رابط الموقع:\nhttps://{domain}\n\nابعته لأهل القرية", disable_web_page_preview=True)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

def run_bot():
    init_db()
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_match_start, pattern='^add_match$')],
        states={
            TEAM1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_team1)],
            TEAM2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_team2)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)],
            STADIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stadium)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(conv_handler)
    app_telegram.add_handler(MessageHandler(filters.Regex(r'^/del_\d+$'), delete_match))
    app_telegram.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    app_telegram.add_handler(CallbackQueryHandler(delete_match_start, pattern='^delete_match$'))
    app_telegram.add_handler(CallbackQueryHandler(list_matches, pattern='^list_matches$'))
    app_telegram.add_handler(CallbackQueryHandler(site_link, pattern='^site_link$'))
    print("الكورة في قرية الصورة شغال...")
    app_telegram.run_polling()

if __name__ == '__main__':
    # شغل البوت في Thread منفصل
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    # شغل الموقع
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
