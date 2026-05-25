const TelegramBot = require('node-telegram-bot-api');

// هات التوكن من Variables في Railway
const token = process.env.BOT_TOKEN;

if (!token) {
  console.log("ERROR: BOT_TOKEN مش موجود في الـ Variables");
  process.exit(1);
}

const bot = new TelegramBot(token, {polling: true});

console.log("Bot is running... ✅");

// أمر /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const name = msg.from.first_name;
  bot.sendMessage(chatId, `أهلاً ${name} 🔥\nالبوت شغال تمام على Railway`);
});

// أمر /help
bot.onText(/\/help/, (msg) => {
  bot.sendMessage(msg.chat.id, "الأوامر المتاحة:\n/start - تشغيل البوت\n/help - المساعدة");
});

// أي رسالة عادية
bot.on('message', (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;
  
  // متردش على الأوامر تاني
  if (text.startsWith('/')) return;
  
  bot.sendMessage(chatId, `انت قولت: ${text}`);
});

// لو حصل ايرور
bot.on('polling_error', (error) => {
  console.log("Polling error:", error.message);
});
