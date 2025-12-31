import os
import json
import shutil
import subprocess
import signal
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# ================= CONFIG =================
BOSS_BOT_TOKEN = "7561581792:AAEJQWH8RlRKryGMuCAJKJaT-oMs37b_5q8"  # Hosting bot ka token
OWNER_ID = 8170937099  # Tera Telegram ID
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
DB_FILE = os.path.join(BASE_DIR, "users.db")
AUTHORIZED_FILE = os.path.join(BASE_DIR, "authorized_users.json")

BOT_FILES = ["spbot5.py", "msg.py"]  # Ye files host.py ke same folder mein rakhna

os.makedirs(USERS_DIR, exist_ok=True)

# ================= AUTHORIZED USERS =================
def load_authorized():
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, 'r') as f:
            return json.load(f)
    else:
        default = [{'id': OWNER_ID, 'username': 'owner'}]
        with open(AUTHORIZED_FILE, 'w') as f:
            json.dump(default, f)
        return default

authorized_users = load_authorized()

def is_authorized(user_id: int) -> bool:
    return any(u['id'] == user_id for u in authorized_users)

def save_authorized():
    with open(AUTHORIZED_FILE, 'w') as f:
        json.dump(authorized_users, f)

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, bot_limit INTEGER)""")
cur.execute("""CREATE TABLE IF NOT EXISTS bots (user_id INTEGER, pid INTEGER, status TEXT, bot_folder TEXT)""")
conn.commit()

def ensure_user(uid: int):
    cur.execute("SELECT bot_limit FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        limit_ = 999999 if uid == OWNER_ID else 1
        cur.execute("INSERT INTO users VALUES (?,?)", (uid, limit_))
        conn.commit()

def running_bot(uid: int):
    cur.execute("SELECT pid, bot_folder FROM bots WHERE user_id=? AND status='running'", (uid,))
    return cur.fetchone()

def running_count(uid: int):
    cur.execute("SELECT COUNT(*) FROM bots WHERE user_id=? AND status='running'", (uid,))
    return cur.fetchone()[0]

# ================= /addbot (Token + Chat ID Maangega) =================
TOKEN, CHAT_ID = range(2)

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return ConversationHandler.END

    ensure_user(uid)
    current_limit = cur.execute("SELECT bot_limit FROM users WHERE user_id=?", (uid,)).fetchone()[0]
    if running_count(uid) >= current_limit:
        await update.message.reply_text("❌ Bot limit reached!")
        return ConversationHandler.END

    await update.message.reply_text("🔑 Apne bot ka BOT_TOKEN bhej:")
    return TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['bot_token'] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Token mila!\n\n"
        "Ab apna Telegram Chat ID bhej (sirf numbers)\n"
        "ID kaise pata kare? @userinfobot ko message kar aur /start daba"
    )
    return CHAT_ID

async def receive_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return ConversationHandler.END

    try:
        user_chat_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid ID! Sirf numbers bhej (jaise 123456789)")
        return CHAT_ID

    token = context.user_data['bot_token']

    # User folder bana
    user_dir = os.path.join(USERS_DIR, f"user_{uid}")
    os.makedirs(user_dir, exist_ok=True)

    # Files copy kar
    for file in BOT_FILES:
        src = os.path.join(BASE_DIR, file)
        if not os.path.exists(src):
            await update.message.reply_text(f"❌ Missing file in main folder: {file}")
            return ConversationHandler.END
        dst = os.path.join(user_dir, file)
        shutil.copy(src, dst)

    # .env bana with token + chat_id
    env_path = os.path.join(user_dir, ".env")
    with open(env_path, "w") as f:
        f.write(f"BOT_TOKEN={token}\n")
        f.write(f"OWNER_TG_ID={user_chat_id}\n")

    # Bot start kar
    proc = subprocess.Popen(["python3", "spbot5.py"], cwd=user_dir)

    # Database mein save
    cur.execute("INSERT OR REPLACE INTO bots VALUES (?, ?, 'running', ?)", (uid, proc.pid, user_dir))
    conn.commit()

    await update.message.reply_text(
        f"✅ Tera bot successfully start ho gaya!\n"
        f"PID: {proc.pid}\n"
        f"Folder: {user_dir}\n\n"
        f"Ab naye bot se /start kar aur test kar le"
    )

    return ConversationHandler.END

# ================= OTHER COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_authorized(uid):
        await update.message.reply_text(
            "✅ Welcome authorized user!\n"
            "/addbot - Naya bot host kar\n"
            "/stop - Band kar\n"
            "/status - Status dekh"
        )
    else:
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return

    row = running_bot(uid)
    if not row:
        await update.message.reply_text("ℹ️ Koi bot chal nahi raha")
        return

    pid, _ = row
    try:
        os.kill(pid, signal.SIGTERM)
    except:
        pass

    cur.execute("UPDATE bots SET status='stopped' WHERE user_id=?", (uid,))
    conn.commit()

    await update.message.reply_text("🛑 Bot band ho gaya")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return

    row = running_bot(uid)
    if row:
        pid, folder = row
        await update.message.reply_text(f"📊 Bot chal raha hai\nPID: {pid}")
    else:
        await update.message.reply_text("ℹ️ Koi bot nahi chal raha")

# ================= ADMIN COMMANDS (Sirf Tu) =================
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /add <tg_id>")
        return
    try:
        tg_id = int(context.args[0])
        if any(u['id'] == tg_id for u in authorized_users):
            await update.message.reply_text("Already authorized")
            return
        authorized_users.append({'id': tg_id, 'username': ''})
        save_authorized()
        await update.message.reply_text(f"✅ {tg_id} ko access de diya")
    except:
        await update.message.reply_text("Invalid ID")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /remove <tg_id>")
        return
    try:
        tg_id = int(context.args[0])
        global authorized_users
        authorized_users = [u for u in authorized_users if u['id'] != tg_id]
        save_authorized()
        await update.message.reply_text(f"❌ {tg_id} ka access hata diya")
    except:
        await update.message.reply_text("Invalid ID")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    msg = "📋 Authorized Users:\n"
    for u in authorized_users:
        msg += f"• {u['id']}\n"
    await update.message.reply_text(msg or "Koi authorized user nahi")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOSS_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("users", list_users))

    conv = ConversationHandler(
        entry_points=[CommandHandler("addbot", addbot)],
        states={
            TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_chat_id)],
        },
        fallbacks=[],
    )
    app.add_handler(conv)

    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    print("Host Bot chal gaya – Access system ON | Token + Chat ID maangega")
    app.run_polling()

if __name__ == "__main__":
    main()
