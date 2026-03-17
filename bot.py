import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import random
import string

# --- ১. কনফিগারেশন ---
BOT_TOKEN = '8743917242:AAG1Ev3j1325D8ZiwhLNOcaKj0Xk1x6hYlI'
ADMIN_ID = 7585875519 
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- Persistent Database Connection ---
DB_FILE = 'premium_investment_final.db'
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

def db_query(query, params=(), fetch=False):
    try:
        cursor.execute(query, params)
        data = cursor.fetchall() if fetch else None
        conn.commit()
        return data
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def init_db():
    db_query(""" CREATE TABLE IF NOT EXISTS users (
        uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0, 
        last_bonus TEXT DEFAULT '', ref_code TEXT UNIQUE, referred_by INTEGER,
        total_ref INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0) """)
    
    db_query(""" CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, plan_id INTEGER, 
        start_date TEXT, end_date TEXT, daily_profit REAL, last_claim TEXT DEFAULT '') """)
    
    db_query(""" CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, type TEXT, 
        amount REAL, info TEXT, date TEXT) """)

    try:
        db_query("ALTER TABLE investments ADD COLUMN end_date TEXT")
    except:
        pass

init_db()

# ==================== ১৫ মিনিট রোটেশন ====================
def get_current_number(method):
    now = datetime.now()
    current_slot = (now.hour * 4) + (now.minute // 15)
    number_list = NUMBERS[method]
    index = current_slot % len(number_list)
    return number_list[index]

def get_remaining_minutes():
    now = datetime.now()
    current_min = now.minute
    next_boundary = ((current_min // 15) + 1) * 15
    return next_boundary - current_min

NUMBERS = {
    'Bkash': ['01864707606', '01906245591', '01735047020'],
    'Nagad': ['01906245591', '01864707606', '01302550839'],
    'Rocket': ['01906245591', '01906475591', '01302550839']
}

USD_RATE = 115.0

PLANS = { i: {'price': p, 'daily': d, 'days': t, 'bonus': b} for i, p, d, t, b in [ 
    (1, 800, 80, 30, 5), (2, 1500, 120, 45, 10), (3, 3000, 200, 60, 20), (4, 5000, 320, 75, 30),
    (5, 8000, 480, 90, 50), (6, 12000, 650, 120, 70), (7, 18000, 900, 150, 100), (8, 25000, 1300, 180, 150),
    (9, 35000, 1800, 210, 200), (10, 50000, 2500, 240, 300), (11, 65000, 3200, 270, 400), (12, 80000, 3900, 300, 500),
    (13, 95000, 4500, 320, 600), (14, 110000, 5200, 340, 750), (15, 120000, 6000, 365, 1000) ] }

# --- Helper Functions ---
def get_method_title(method):
    if method == "Bkash": return "📱 বিকাশ (Personal)"
    elif method == "Nagad": return "🟠 নগদ (Personal)"
    elif method == "Rocket": return "🚀 রকেট (Personal)"
    else: return "🪙 USDT (TRC20)"

def get_withdraw_title(method):
    if method == "Bkash": return "📱 বিকাশ"
    elif method == "Nagad": return "🟠 নগদ"
    elif method == "Rocket": return "🚀 রকেট"
    else: return "🪙 USDT"

def main_menu(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("📊 ব্যালেন্স 💰", "📈 ইনভেস্ট প্ল্যান 🚀")
    markup.add("📊 My Investments 📋", "📥 জমা করুন 💳")
    markup.add("📤 উত্তোলন করুন 🏦", "💼 আমার কাজ/দৈনিক টাক্স 📂")
    markup.add("🔗 রেফারেল 👥", "🎁 ডেইলি বোনাস ✨")
    markup.add("📜 লেনদেন হিস্টরি 📑", "💬 সাপোর্ট ও সাহায্য 🎧")
    if uid == ADMIN_ID: markup.add("⚙️ কন্ট্রোলার প্যানেল 🛠")
    return markup

def is_user_valid(uid):
    res = db_query("SELECT is_blocked FROM users WHERE uid=?", (uid,), fetch=True)
    return not (res and res[0][0] == 1)

def get_user_bonus_amount(uid):
    res = db_query("SELECT plan_id FROM investments WHERE uid=? ORDER BY plan_id DESC LIMIT 1", (uid,), fetch=True)
    return PLANS[res[0][0]]['bonus'] if res else 0

# --- ফেক লিডারবোর্ড (শুধু User ID + প্রতিবার বাড়বে) ---
fake_user_ids = [987654321, 1122334455, 5566778899, 2233445566, 7788990011, 3344556677, 8899001122, 4455667788, 6677889900, 9900112233]
fake_ref_counts = [2450, 1890, 1675, 1430, 1320, 1285, 1150, 1090, 1055, 1020]

# --- মেসেজ হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    if not is_user_valid(uid):
        bot.send_message(uid, "🚫 <b>দুঃখিত! আপনাকে ব্লক করা হয়েছে।</b>")
        return
    
    res = db_query("SELECT uid FROM users WHERE uid=?", (uid,), fetch=True)
    if not res:
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ref_by_uid = None
        if len(message.text.split()) > 1:
            possible_ref = message.text.split()[1].strip()
            ref_check = db_query("SELECT uid FROM users WHERE ref_code=?", (possible_ref,), fetch=True)
            if ref_check:
                ref_by_uid = ref_check[0][0]
        db_query("INSERT INTO users (uid, ref_code, referred_by) VALUES (?, ?, ?)", (uid, ref_code, ref_by_uid))
    
    welcome_txt = """🔥 <b>স্বাগতম PREMIUM INCOME BD-তে!</b> 🔥
━━━━━━━━━━━━━━━━━━━━
আপনার স্বপ্নকে সত্যি করতে এবং ঘরে বসে নিরাপদ আয়ের নিশ্চয়তা নিয়ে আমরা এসেছি আপনার পাশে।

✨ <b>আমাদের বিশেষত্ব:</b> ✨
✅ <b>সহজ বিনিয়োগ:</b> মাত্র ৮০০ টাকা থেকে শুরু।
✅ <b>নিশ্চিত আয়:</b> প্রতিদিন আপনার একাউন্টে লাভ যোগ হবে।
✅ <b>দ্রুত পেমেন্ট:</b> মাত্র ৮ ঘণ্টার মধ্যে উইথড্র সফল।
✅ <b>রেফার বোনাস:</b> বন্ধুদের ইনভাইট করলেই পাচ্ছেন আকর্ষণীয় বোনাস।

আমাদের সাথে আপনার যাত্রা হোক লাভজনক ও আনন্দময়!"""
    bot.send_message(uid, welcome_txt, reply_markup=main_menu(uid))

@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    uid, txt = message.chat.id, message.text
    if not is_user_valid(uid): return

    if "📊 ব্যালেন্স" in txt:
        res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        bal = res[0][0] if res else 0.0
        balance_msg = f"""💰 <b>আপনার বর্তমান ব্যালেন্স</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━

         ➡️➡️➡️ ৳ {bal:,.2f} 💳

━━━━━━━━━━━━━━━━━━━━━━━━━━━

• মোট ব্যালেন্স 💰: <b>৳{bal:,.2f}</b>
• উপলব্ধ উত্তোলন 💰: <b>৳{max(0, bal):,.2f}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>টিপস:</b>
• সর্বনিম্ন উত্তোলন: ৳৫০০
• উত্তোলন করতে "উত্তোলন করুন" বাটনে চাপুন
• আরও ব্যালেন্স যোগ করতে "জমা করুন" ব্যবহার করুন

সফলতার জন্য শুভকামনা! 🚀"""
        bot.send_message(uid, balance_msg)

    elif "📈 ইনভেস্ট প্ল্যান" in txt:
        msg = "💎 <b>আমাদের প্রিমিয়াম ইনভেস্টমেন্ট প্ল্যানসমূহ:</b>\n"
        msg += "⚠️ <i>মনে রাখবেন: বড় প্যাকেজে ডেইলি বোনাসও বেশি!</i>\n"
        for pid, p in PLANS.items():
            total = p['daily'] * p['days']
            msg += f"\n┌─────────────────────────┐\n💼 <b>ইনভেস্ট প্ল্যান – {pid:02}</b>\n💰 ইনভেস্ট: ৳{p['price']:,}\n⏳ মেয়াদ: {p['days']} দিন\n💵 দৈনিক আয়: ৳{p['daily']:,}\n🎁 ডেইলি বোনাস: ৳{p['bonus']}\n📊 মোট পাবেন: ৳{total:,}\n└─────────────────────────┘\n"
        bot.send_message(uid, msg + "\n📝 <b>আপনি কত নম্বর প্যাকেজটি নিতে চান? শুধু নম্বরটি লিখে পাঠান (যেমন: 1, 2, 5)</b>")
        bot.register_next_step_handler(message, process_buy_plan)

    elif "🔗 রেফারেল" in txt:
        has_package = bool(db_query("SELECT id FROM investments WHERE uid=?", (uid,), fetch=True))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎟️ রেফারেল কোড নিন", callback_data="get_ref_code"))
        
        text = """👥 <b>রেফারেল সেকশন</b>
━━━━━━━━━━━━━━━━━━━━
✅ এখান থেকে বন্ধুদের ইনভাইট করুন
✅ প্রতি সফল রেফারে পাবেন ৳৫০ বোনাস

"""
        if has_package:
            res = db_query("SELECT ref_code, total_ref FROM users WHERE uid=?", (uid,), fetch=True)
            ref_link = f"https://t.me/{bot.get_me().username}?start={res[0][0]}"
            text += f"🔗 আপনার রেফার লিঙ্ক:\n<code>{ref_link}</code>\n🎟️ আপনার কোড: <code>{res[0][0]}</code>\n👥 মোট রেফার: {res[0][1]} জন\n"
        else:
            text += "❌ রেফারেল কোড পেতে প্রথমে একটি প্যাকেজ কিনুন।"

        global fake_ref_counts
        increase = random.randint(5, 10)
        for i in range(len(fake_ref_counts)):
            fake_ref_counts[i] += random.randint(5, 10)
        
        lb = f"""🔴 এই মুহূর্তে +{increase} রেফার বেড়েছে!\n\n🏆 <b>টপ ১০ রেফারার (লাইভ)</b>\n"""
        for rank, (uid_fake, count) in enumerate(zip(fake_user_ids, fake_ref_counts), 1):
            lb += f"{rank}. User-{uid_fake} → {count:,} জন\n"
        
        bot.send_message(uid, text + lb, reply_markup=markup)

    elif "📊 My Investments" in txt:
        invs = db_query("SELECT id, plan_id, start_date, end_date, daily_profit FROM investments WHERE uid=?", (uid,), fetch=True)
        if not invs:
            bot.send_message(uid, "❌ আপনার কোনো ইনভেস্টমেন্ট নেই।")
            return
        msg = "📋 <b>আপনার সব ইনভেস্টমেন্ট:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for i in invs:
            days_left = (datetime.strptime(i[3], '%Y-%m-%d') - datetime.now()).days if i[3] else 0
            total_profit = i[4] * (PLANS[i[1]]['days'] - days_left)
            msg += f"🔹 প্যাকেজ {i[1]} | বাকি: {days_left} দিন | দৈনিক: ৳{i[4]:,} | মোট প্রফিট: ৳{total_profit:,}\n"
        bot.send_message(uid, msg)

    elif "📥 জমা করুন" in txt:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📱 বিকাশ", callback_data="depo_method_Bkash"),
                   types.InlineKeyboardButton("🟠 নগদ", callback_data="depo_method_Nagad"),
                   types.InlineKeyboardButton("🚀 রকেট", callback_data="depo_method_Rocket"),
                   types.InlineKeyboardButton("🪙 USDT (TRC20)", callback_data="depo_method_USDT"))
        bot.send_message(uid, """💳 <b>ডিপোজিট মেথড নির্বাচন করুন</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
নিচের যেকোনো একটি পেমেন্ট মেথড বেছে নিন:""", reply_markup=markup)

    elif "📤 উত্তোলন করুন" in txt:
        res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        bal = res[0][0] if res else 0.0
        if bal < 500:
            bot.send_message(uid, f"""❌ <b>উত্তোলন করা যাবে না</b>

💰 বর্তমান ব্যালেন্স: ৳{bal:,.2f}
⚠️ সর্বনিম্ন উত্তোলন: ৳৫০০""")
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📱 বিকাশ", callback_data="wd_method_Bkash"),
                   types.InlineKeyboardButton("🟠 নগদ", callback_data="wd_method_Nagad"),
                   types.InlineKeyboardButton("🚀 রকেট", callback_data="wd_method_Rocket"),
                   types.InlineKeyboardButton("🪙 USDT", callback_data="wd_method_USDT"))
        bot.send_message(uid, f"""🏦 <b>উত্তোলন করুন</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 বর্তমান ব্যালেন্স: <b>৳{bal:,.2f}</b>
⚠️ সর্বনিম্ন: ৳৫০০

নিচের যেকোনো একটি মেথড বেছে নিন:""", reply_markup=markup)

    elif "💼 আমার কাজ" in txt:
        invs = db_query("SELECT id, plan_id, daily_profit, last_claim, end_date FROM investments WHERE uid=?", (uid,), fetch=True)
        if not invs:
            bot.send_message(uid, "❌ আপনার কোনো সক্রিয় প্যাকেজ নেই।")
            return
        today_str = datetime.now().strftime('%Y-%m-%d')
        for i in invs:
            if i[4] and i[4] < today_str:
                bot.send_message(uid, f"❌ প্যাকেজ {i[1]} এর মেয়াদ শেষ ({i[4]})")
                continue
            btn_text = "✅ আজকের কাজ শেষ" if i[3] == today_str else "💰 প্রফিট সংগ্রহ করুন"
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(btn_text, callback_data=f"claim_{i[0]}"))
            bot.send_message(uid, f"💼 <b>প্যাকেজ নং: {i[1]}</b>\n💸 দৈনিক আয়: ৳{i[2]}\n📅 মেয়াদ: {i[4]}", reply_markup=markup)

    elif "🎁 ডেইলি বোনাস" in txt:
        bonus_amt = get_user_bonus_amount(uid)
        if bonus_amt == 0:
            bot.send_message(uid, "❌ <b>বোনাস পেতে আপনাকে অবশ্যই একটি ইনভেস্ট প্ল্যান কিনতে হবে। প্যাকেজের দাম যত বেশি বোনাসও তত বেশি!</b>")
            return
        res = db_query("SELECT last_bonus FROM users WHERE uid=?", (uid,), fetch=True)
        today = datetime.now().strftime('%Y-%m-%d')
        if res and res[0][0] == today:
            bot.send_message(uid, "❌ আপনি আজ অলরেডি বোনাস নিয়েছেন। আগামীকাল আবার চেষ্টা করুন।")
        else:
            db_query("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE uid = ?", (bonus_amt, today, uid))
            bot.send_message(uid, f"✅ অভিনন্দন! আপনি আপনার প্যাকেজ অনুযায়ী আজ <b>৳{bonus_amt}</b> ডেইলি বোনাস পেয়েছেন।")

    elif "📜 লেনদেন হিস্টরি" in txt:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📥 ডিপোজিট হিস্টরি", callback_data="hist_depo"),
                   types.InlineKeyboardButton("📤 উত্তোলন হিস্টরি", callback_data="hist_with"),
                   types.InlineKeyboardButton("💼 প্যাকেজ হিস্টরি", callback_data="hist_pack"))
        history_msg = f"""📜 <b>লেনদেন হিস্টরি</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━

আপনার লেনদেনের ধরন নির্বাচন করুন:

• ডিপোজিট হিস্টরি → জমা করা লেনদেন দেখুন
• উত্তোলন হিস্টরি → উত্তোলনের রেকর্ড দেখুন
• প্যাকেজ হিস্টরি → কেনা প্যাকেজের তথ্য দেখুন

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>টিপস:</b>
• সর্বোচ্চ ১০টি সাম্প্রতিক লেনদেন দেখানো হবে
• বিস্তারিত দেখতে উপরের বাটনে চাপুন

সবকিছু সঠিকভাবে যাচাই করে লেনদেন করুন।"""
        bot.send_message(uid, history_msg, reply_markup=markup)

    elif "💬 সাপোর্ট ও সাহায্য" in txt:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Admin Support", url="https://t.me/PremiumSupport_26"))
        bot.send_message(uid, "🎧 কোনো সমস্যা বা পেমেন্ট সংক্রান্ত সাহায্যের জন্য নিচের বাটনে ক্লিক করে এডমিনের সাথে যোগাযোগ করুন।", reply_markup=markup)

    elif "⚙️ কন্ট্রোলার প্যানেল" in txt and uid == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📢 সকল ইউজারকে নোটিশ", callback_data="adm_broadcast"),
                   types.InlineKeyboardButton("🚫 ইউজার ব্লক/আনব্লক", callback_data="adm_block"),
                   types.InlineKeyboardButton("💰 ব্যালেন্স অ্যাড/কাটা", callback_data="adm_edit_bal"))
        bot.send_message(uid, "🛠 <b>এডমিন কন্ট্রোল সেন্টার</b>", reply_markup=markup)

# --- process_buy_plan ---
def process_buy_plan(message):
    try:
        pid = int(message.text)
        uid = message.chat.id
        if pid in PLANS:
            p = PLANS[pid]
            res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
            if res and res[0][0] >= p['price']:
                now = datetime.now()
                start_d = now.strftime('%Y-%m-%d')
                end_d = (now + timedelta(days=p['days'])).strftime('%Y-%m-%d')
                db_query("UPDATE users SET balance = balance - ? WHERE uid = ?", (p['price'], uid))
                db_query("INSERT INTO investments (uid, plan_id, start_date, end_date, daily_profit) VALUES (?, ?, ?, ?, ?)", (uid, pid, start_d, end_d, p['daily']))
                db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", (uid, 'PACK', p['price'], f"প্যাকেজ {pid}", datetime.now().strftime('%Y-%m-%d %H:%M')))
                ref_res = db_query("SELECT referred_by FROM users WHERE uid=?", (uid,), fetch=True)
                if ref_res and ref_res[0][0]:
                    db_query("UPDATE users SET balance = balance + 50, total_ref = total_ref + 1 WHERE uid = ?", (ref_res[0][0],))
                bot.send_message(uid, f"✅ অভিনন্দন! প্যাকেজ {pid} সক্রিয় হয়েছে।")
                notice = f"""🌟 <b>প্রিমিয়াম আপডেট নোটিশ</b> 🌟
━━━━━━━━━━━━━━━━━━━━
অভিনন্দন! আপনি {pid} নং প্যাকেজটি কিনেছেন। 

🚀 <b>আপনার নতুন সুবিধা:</b>
✅ এখন থেকে আপনি প্রতি রেফারে পাবেন <b>৳৫০</b>।
✅ আপনার ডেইলি বোনাস এখন থেকে <b>৳{PLANS[pid]['bonus']}</b>।
💡 <i>টিপস: যত বড় প্যাকেজ কিনবেন, আপনার ডেইলি বোনাস তত বৃদ্ধি পাবে!</i>
━━━━━━━━━━━━━━━━━━━━"""
                bot.send_message(uid, notice)
            else:
                bot.send_message(uid, "❌ পর্যাপ্ত ব্যালেন্স নেই।")
    except:
        bot.send_message(message.chat.id, "❌ ভুল নম্বর!")

# --- Deposit Functions ---
def process_deposit_amount(message, method):
    uid = message.chat.id
    try:
        amt = float(message.text.strip())
        min_amt = 10 if method == "USDT" else 800
        if amt < min_amt:
            bot.send_message(uid, f"❌ সর্বনিম্ন {min_amt} {'$' if method=='USDT' else '৳'} জমা করতে হবে। আবার চেষ্টা করুন।")
            return
        if method == "USDT":
            number = "TMbcaNfCmm3LsbtMsw5sFXSfdAJ4ibA3WN"
            timer_line = ""
            min_text = "$১০"
            display_amt = f"${amt:,.2f} USDT (≈ ৳{amt * USD_RATE:,.2f})"
        else:
            number = get_current_number(method)
            remaining = get_remaining_minutes()
            timer_line = f"🔄 এই নম্বর আর <b>{remaining}</b> মিনিট পর চেঞ্জ হবে ⏳"
            min_text = "৳৮০০"
            display_amt = f"৳{amt:,.2f}"
        title = get_method_title(method)
        depo_info = f"""<b>💳 {title}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{timer_line}

┌───────────────────────────────┐
│ <b>{title}</b>           │
│ <code>{number}</code>   │
│ 🔸 মিনিমাম: {min_text}                   │
└───────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>গুরুত্বপূর্ণ:</b>
• Send Money / Transfer করে পেমেন্ট সম্পন্ন করুন
• এখন **ট্রানজেকশন আইডি** অথবা **স্ক্রিনশট** (যেকোনো একটা) পাঠান

📌 আপনার এমাউন্ট: <b>{display_amt}</b>"""
        bot.send_message(uid, depo_info)
        bot.register_next_step_handler(message, process_deposit_proof, method, amt, number)
    except:
        bot.send_message(uid, "❌ সঠিক সংখ্যা লিখুন (যেমন: 1500)")

def process_deposit_proof(message, method, amt, number):
    uid = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Accept", callback_data=f"depo_acc_{uid}_{amt}_{method}"),
               types.InlineKeyboardButton("❌ Cancel", callback_data=f"depo_can_{uid}_{amt}_{method}"))
    if message.content_type == 'photo':
        caption = f"""🔔 <b>নতুন ডিপোজিট রিকোয়েস্ট</b>
UID: <code>{uid}</code>
মেথড: {method}
অ্যামাউন্ট: ৳{amt:,.2f}
নম্বর: {number}
প্রুফ: স্ক্রিনশট"""
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    else:
        txid = message.text.strip()
        text_msg = f"""🔔 <b>নতুন ডিপোজিট রিকোয়েস্ট</b>
UID: <code>{uid}</code>
মেথড: {method}
অ্যামাউন্ট: ৳{amt:,.2f}
নম্বর: {number}
ট্রানজেকশন আইডি: {txid}"""
        bot.send_message(ADMIN_ID, text_msg, reply_markup=markup)
    bot.send_message(uid, "⏳ আপনার ডিপোজিট রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে। যাচাই করে ব্যালেন্স যোগ করা হবে।")

# --- Withdraw Functions ---
def process_withdraw_amount_new(message, method):
    uid = message.chat.id
    try:
        amt = float(message.text.strip())
        if amt < 500:
            bot.send_message(uid, "❌ সর্বনিম্ন ৳৫০০")
            return
        bal_res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        bal = bal_res[0][0] if bal_res else 0.0
        if amt > bal:
            bot.send_message(uid, f"❌ পর্যাপ্ত ব্যালেন্স নেই। বর্তমান: ৳{bal:,.2f}")
            return
        msg = bot.send_message(uid, f"📝 আপনার {get_withdraw_title(method)} নম্বর / অ্যাড্রেস দিন:")
        bot.register_next_step_handler(msg, process_withdraw_details, method, amt)
    except:
        bot.send_message(uid, "❌ সঠিক সংখ্যা লিখুন।")

def process_withdraw_details(message, method, amt):
    uid = message.chat.id
    details = message.text.strip()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Confirm", callback_data=f"wd_confirm_{uid}_{amt}_{method}_{details}"),
               types.InlineKeyboardButton("❌ Cancel", callback_data=f"wd_cancel_{uid}_{amt}"))
    summary = f"""🏦 <b>উত্তোলনের সামারি</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
মেথড: <b>{get_withdraw_title(method)}</b>
পরিমাণ: <b>৳{amt:,.2f}</b>
নম্বর/অ্যাড্রেস: <code>{details}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Confirm চাপলে এডমিনের কাছে পাঠানো হবে"""
    bot.send_message(uid, summary, reply_markup=markup)

# --- Callback Handler (পুরোপুরি) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_logic(call):
    data = call.data
    uid = call.message.chat.id

    if data == "get_ref_code":
        has_package = bool(db_query("SELECT id FROM investments WHERE uid=?", (uid,), fetch=True))
        if has_package:
            res = db_query("SELECT ref_code FROM users WHERE uid=?", (uid,), fetch=True)
            bot.answer_callback_query(call.id, f"✅ আপনার কোড: {res[0][0]}", show_alert=True)
            bot.send_message(uid, f"🎟️ আপনার রেফারেল কোড:\n<code>{res[0][0]}</code>")
        else:
            bot.answer_callback_query(call.id, "❌ প্রথমে প্যাকেজ কিনুন!", show_alert=True)

    elif data.startswith("depo_method_"):
        method = data.split("_")[-1]
        bot.answer_callback_query(call.id)
        prompt = bot.send_message(uid, f"""💰 <b>{get_method_title(method)}</b> এর মাধ্যমে ডিপোজিট

━━━━━━━━━━━━━━━━━━━━━━━━━━━
{'কত USDT জমা করতে চান?' if method == 'USDT' else 'আপনি কত টাকা জমা করতে চান?'}

🔸 সর্বনিম্ন: {'$১০' if method == 'USDT' else '৳৮০০'}""")
        bot.register_next_step_handler(prompt, process_deposit_amount, method)

    elif data.startswith("depo_acc_") or data.startswith("depo_can_"):
        parts = data.split("_")
        action = parts[1]
        target_uid = int(parts[2])
        amt = float(parts[3])
        method = "_".join(parts[4:]) if len(parts) > 4 else ""
        if action == "acc":
            final_amount = amt * USD_RATE if method == "USDT" else amt
            db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (final_amount, target_uid))
            db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                     (target_uid, 'DEPO', final_amount, f"এডমিন এপ্রুভড ({method})", datetime.now().strftime('%Y-%m-%d %H:%M')))
            bot.send_message(target_uid, f"✅ এডমিন আপনার <b>৳{final_amount:,.2f}</b> ডিপোজিট ({method}) সফলভাবে যুক্ত করেছে।")
            success_text = f"✅ অনুমোদিত: ৳{final_amount:,.2f} ({method})"
            if call.message.content_type == 'photo':
                bot.edit_message_caption(success_text, ADMIN_ID, call.message.message_id)
            else:
                bot.edit_message_text(success_text, ADMIN_ID, call.message.message_id)
        else:
            bot.send_message(target_uid, f"❌ আপনার ৳{amt:,.2f} ডিপোজিট রিকোয়েস্ট বাতিল করা হয়েছে।")
            cancel_text = f"❌ বাতিল: ৳{amt:,.2f} ({method})"
            if call.message.content_type == 'photo':
                bot.edit_message_caption(cancel_text, ADMIN_ID, call.message.message_id)
            else:
                bot.edit_message_text(cancel_text, ADMIN_ID, call.message.message_id)

    elif data.startswith("wd_method_"):
        method = data.split("_")[-1]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(uid, f"""💰 <b>{get_withdraw_title(method)}</b> এর মাধ্যমে উত্তোলন

━━━━━━━━━━━━━━━━━━━━━━━━━━━
কত টাকা উত্তোলন করতে চান?

🔸 সর্বনিম্ন: ৳৫০০""")
        bot.register_next_step_handler(msg, process_withdraw_amount_new, method)

    elif data.startswith("wd_confirm_"):
        parts = data.split("_")
        target_uid = int(parts[2])
        amt = float(parts[3])
        method = parts[4]
        details = "_".join(parts[5:]) if len(parts) > 5 else ""
        db_query("UPDATE users SET balance = balance - ? WHERE uid = ?", (amt, target_uid))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Accept", callback_data=f"wd_acc_{target_uid}_{amt}_{method}"),
                   types.InlineKeyboardButton("❌ Cancel", callback_data=f"wd_can_{target_uid}_{amt}"))
        bot.send_message(ADMIN_ID, f"""📤 <b>নতুন উইথড্র রিকোয়েস্ট</b>
UID: <code>{target_uid}</code>
মেথড: {method}
পরিমাণ: ৳{amt:,.2f}
তথ্য: {details}""", reply_markup=markup)
        bot.send_message(target_uid, f"💸 ৳{amt:,.2f} ব্যালেন্স থেকে কাটা হয়েছে। এডমিন যাচাই করছে...")

    elif data.startswith("wd_cancel_"):
        bot.send_message(uid, "❌ উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে।")

    elif data.startswith("wd_acc_"):
        parts = data.split("_")
        target_uid = int(parts[2])
        amt = float(parts[3])
        method = parts[4]
        db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                 (target_uid, 'WITH', amt, f"উত্তোলন ({method}) সফল", datetime.now().strftime('%Y-%m-%d %H:%M')))
        bot.send_message(target_uid, f"✅ আপনার ৳{amt:,.2f} উত্তোলন ({method}) সফল হয়েছে!")
        bot.edit_message_text(f"✅ অনুমোদিত: ৳{amt:,.2f} ({method})", ADMIN_ID, call.message.message_id)

    elif data.startswith("wd_can_"):
        parts = data.split("_")
        target_uid = int(parts[2])
        amt = float(parts[3])
        db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (amt, target_uid))
        bot.send_message(target_uid, f"❌ ৳{amt:,.2f} উত্তোলন বাতিল। টাকা ফেরত দেওয়া হয়েছে।")
        bot.edit_message_text(f"❌ বাতিল: ৳{amt:,.2f}", ADMIN_ID, call.message.message_id)

    elif data.startswith("claim_"):
        inv_id = data.split("_")[1]
        res = db_query("SELECT daily_profit, last_claim, end_date FROM investments WHERE id=?", (inv_id,), fetch=True)
        if not res: return
        daily, last, end_d = res[0]
        today = datetime.now().strftime('%Y-%m-%d')
        if end_d and end_d < today:
            bot.answer_callback_query(call.id, "❌ প্যাকেজ মেয়াদ শেষ!", show_alert=True)
            return
        if last == today:
            bot.answer_callback_query(call.id, "❌ আজকে ইতিমধ্যে নিয়েছেন!", show_alert=True)
            return
        db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (daily, uid))
        db_query("UPDATE investments SET last_claim = ? WHERE id = ?", (today, inv_id))
        bot.edit_message_text(f"✅ আজকের লাভ ৳{daily} যুক্ত হয়েছে।", uid, call.message.message_id)

    elif data.startswith("hist_"):
        h_type = data.split("_")[1]
        t_map = {'depo': 'DEPO', 'with': 'WITH', 'pack': 'PACK'}
        db_type = t_map[h_type]
        results = db_query("SELECT amount, info, date FROM history WHERE uid=? AND type=? ORDER BY id DESC LIMIT 10", (uid, db_type), fetch=True)
        if not results:
            bot.send_message(uid, f"""📭 <b>{db_type} হিস্টরি</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
কোনো লেনদেন পাওয়া যায়নি।""")
            return
        h_msg = f"""📜 <b>{db_type} হিস্টরি (সাম্প্রতিক ১০টি)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"""
        for i, r in enumerate(results, 1):
            h_msg += f"""┌──── লেনদেন #{i} ─────┐
│ 📅 তারিখ: {r[2]} │
│ 💰 পরিমাণ: ৳{r[0]:,.2f} │
│ ℹ️ বিবরণ: {r[1]} │
└─────────────────────┘\n"""
        h_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 সর্বোচ্চ সাম্প্রতিক ১০টি লেনদেন দেখানো হচ্ছে।"
        bot.send_message(uid, h_msg)

    elif data == "adm_broadcast":
        msg = bot.send_message(ADMIN_ID, "📢 সকল ইউজারকে পাঠানোর জন্য নোটিশটি লিখুন:")
        bot.register_next_step_handler(msg, admin_broadcast_msg)
    elif data == "adm_block":
        msg = bot.send_message(ADMIN_ID, "ব্লক করতে: `ID block` | আনব্লক করতে: `ID unblock` লিখুন।")
        bot.register_next_step_handler(msg, admin_block_user)
    elif data == "adm_edit_bal":
        msg = bot.send_message(ADMIN_ID, """💰 <b>ব্যালেন্স সেট করুন</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
ফরম্যাট: <code>USER_ID amount</code>

উদাহরণ:
7585875519 500

⚠️ এটি পুরো ব্যালেন্স ওভাররাইট করবে""")
        bot.register_next_step_handler(msg, admin_set_balance)

# --- এডমিন ফাংশন ---
def admin_broadcast_msg(message):
    users = db_query("SELECT uid FROM users", fetch=True)
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 <b>অফিশিয়াল নোটিশ</b>\n\n{message.text}")
            count += 1
        except: continue
    bot.send_message(ADMIN_ID, f"✅ {count} জন ইউজারকে নোটিশ পাঠানো হয়েছে।")

def admin_block_user(message):
    try:
        parts = message.text.split()
        target_id, action = int(parts[0]), parts[1].lower()
        val = 1 if action == "block" else 0
        db_query("UPDATE users SET is_blocked = ? WHERE uid = ?", (val, target_id))
        bot.send_message(ADMIN_ID, f"✅ ইউজার {target_id} সফলভাবে {action} করা হয়েছে।")
    except: 
        bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল!")

def admin_set_balance(message):
    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        new_balance = float(parts[1])
        old_res = db_query("SELECT balance FROM users WHERE uid=?", (target_id,), fetch=True)
        old_bal = old_res[0][0] if old_res else 0.0
        db_query("UPDATE users SET balance = ? WHERE uid = ?", (new_balance, target_id))
        db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                 (target_id, 'ADMIN_SET', new_balance, f"এডমিন সেট করেছে (পুরনো: ৳{old_bal:,.2f})", 
                  datetime.now().strftime('%Y-%m-%d %H:%M')))
        bot.send_message(ADMIN_ID, f"""✅ সফল!
━━━━━━━━━━━━━━━━━━━━
ইউজার: <code>{target_id}</code>
পুরনো: ৳{old_bal:,.2f}
নতুন: <b>৳{new_balance:,.2f}</b>""")
        try:
            bot.send_message(target_id, f"""🛠 <b>এডমিন আপডেট</b>
━━━━━━━━━━━━━━━━━━━━
আপনার ব্যালেন্স সেট করা হয়েছে:
<b>৳{new_balance:,.2f}</b>""")
        except:
            pass
    except:
        bot.send_message(ADMIN_ID, """❌ ফরম্যাট ভুল!

সঠিক ফরম্যাট:
USER_ID amount

উদাহরণ:
7585875519 500""")

# --- শেষ ---
print("--- Premium Investment Bot (Full Complete + Live User ID Leaderboard) is Online! ---")
bot.infinity_polling()