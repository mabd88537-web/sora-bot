const TelegramBot = require('node-telegram-bot-api');
const { initializeApp } = require('firebase/app');
const { getDatabase, ref, set, get, update } = require('firebase/database');

const token = '8966607781:AAGkDgoGtqfANcpzBaqkUOd26BftPx1Vpao';

const firebaseConfig = {
  apiKey: "AIzaSyAKhWBZZZ3u-MuanzESGG-t4oGH__RK2z0",
  authDomain: "sora-b2649.firebaseapp.com",
  databaseURL: "https://sora-b2649-default-rtdb.firebaseio.com",
  projectId: "sora-b2649",
  storageBucket: "sora-b2649.firebasestorage.app",
  messagingSenderId: "1076756814603",
  appId: "1:1076756814603:web:675f724976091d9cd5600e"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);
const bot = new TelegramBot(token, {polling: true});

console.log('البوت شغال 🔥');

// مثال: أمر /add يدوي
bot.onText(/\/add (.+) (\d+)/, async (msg, match) => {
  const name = match[1];
  const goals = parseInt(match[2]);
  await update(ref(db, 'players/' + name), {
    goals: goals
  });
  bot.sendMessage(msg.chat.id, `تم تحديث ${name}: ${goals} جول`);
});