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
BOSS_BOT_TOKEN = "7561581792:AAEJQWH8RlRKryGMuCAJKJaT-oMs37b_5q8"
OWNER_ID = 8170937099
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
DB_FILE = os.path.join(BASE_DIR, "users.db")
AUTHORIZED_FILE = os.path.join(BASE_DIR, "authorized_users.json")

BOT_FILES = ["spbot5.py", "msg.py"]

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

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_authorized(uid):
        await update.message.reply_text("✅ Welcome!\n/addbot - Host new bot\n/stop - Stop\n/status - Check")
    else:
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return

    row = running_bot(uid)
    if not row:
        await update.message.reply_text("No bot running")
        return

    pid, _ = row
    try:
        os.kill(pid, signal.SIGTERM)
    except:
        pass

    cur.execute("UPDATE bots SET status='stopped' WHERE user_id=?", (uid,))
    conn.commit()

    await update.message.reply_text("🛑 Bot stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return

    row = running_bot(uid)
    if row:
        pid, folder = row
        await update.message.reply_text(f"Running\nPID: {pid}")
    else:
        await update.message.reply_text("No bot running")

# ================= ADMIN =================
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /add <tg_id>")
        return
    try:
        tg_id = int(context.args[0])
        if any(u['id'] == tg_id for u in authorized_users):
            await update.message.reply_text("Already added")
            return
        authorized_users.append({'id': tg_id, 'username': ''})
        save_authorized()
        await update.message.reply_text(f"Added {tg_id}")
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
        await update.message.reply_text(f"Removed {tg_id}")
    except:
        await update.message.reply_text("Invalid ID")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    msg = "Authorized Users:\n"
    for u in authorized_users:
        msg += f"• {u['id']}\n"
    await update.message.reply_text(msg or "No users")

# ================= /addbot =================
TOKEN, CHAT_ID = range(2)

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return ConversationHandler.END

    ensure_user(uid)
    if running_count(uid) >= cur.execute("SELECT bot_limit FROM users WHERE user_id=?", (uid,)).fetchone()[0]:
        await update.message.reply_text("Bot limit reached!")
        return ConversationHandler.END

    await update.message.reply_text("🔑 BOT_TOKEN bhej:")
    return TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['bot_token'] = update.message.text.strip()
    await update.message.reply_text("Token mila!\nAb Chat ID bhej (@userinfobot se)")
    return CHAT_ID

async def receive_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⚠️ You are not authorised to use, dm owner to gain access! @sammy_here01 ⚠️")
        return ConversationHandler.END

    try:
        user_chat_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Invalid ID! Sirf numbers")
        return CHAT_ID

    token = context.user_data['bot_token']

    user_dir = os.path.join(USERS_DIR, f"user_{uid}")
    os.makedirs(user_dir, exist_ok=True)

    for file in BOT_FILES:
        src = os.path.join(BASE_DIR, file)
        dst = os.path.join(user_dir, file)
        shutil.copy(src, dst)

    # Alag venv bana
    venv_dir = os.path.join(user_dir, "venv")
    subprocess.run(["python3", "-m", "venv", venv_dir], check=True)

    user_python = os.path.join(venv_dir, "bin", "python")

    # Libraries auto install
    await update.message.reply_text("⏳ Libraries install ho rahi hain... (1-2 min)")
    install_cmd = [
        user_python, "-m", "pip", "install",
        "python-telegram-bot", "instagrapi", "playwright", "playwright-stealth", "python-dotenv", "psutil"
    ]
    subprocess.run(install_cmd, check=True)

    # Playwright browser install
    subprocess.run([user_python, "-m", "playwright", "install", "chromium"], check=True)
    subprocess.run([user_python, "-m", "playwright", "install-deps", "chromium"], check=True)

    # .env bana
    env_path = os.path.join(user_dir, ".env")
    with open(env_path, "w") as f:
        f.write(f"BOT_TOKEN={token}\n")
        f.write(f"OWNER_TG_ID={user_chat_id}\n")

    # Bot start
    proc = subprocess.Popen([user_python, "spbot5.py"], cwd=user_dir)

    cur.execute("INSERT OR REPLACE INTO bots VALUES (?, ?, 'running', ?)", (uid, proc.pid, user_dir))
    conn.commit()

    await update.message.reply_text(f"Bot hosted!\nPID: {proc.pid}\n/start kar naye bot se")

    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOSS_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
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

    print("Host Bot Started")
    app.run_polling()

if __name__ == "__main__":
    main()
