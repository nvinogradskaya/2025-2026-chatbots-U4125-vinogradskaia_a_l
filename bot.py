import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import logging

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "tasks.db"

TASK_TEXT, TASK_PRIORITY = range(2)

PRIORITY_MAP = {
    "высокий": 3,
    "средний": 2,
    "низкий": 1,
}


# ================= DB =================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_task(user_id: int, text: str, priority: str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO tasks (user_id, text, priority, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, text, priority, datetime.now().strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()


def get_tasks(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, text, priority, created_at
        FROM tasks
        WHERE user_id = ?
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return rows


def delete_db_on_start():
    # ⚠️ только для учебного проекта
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 To-Do бот\n\n"
        "/add — добавить задачу\n"
        "/list — список задач\n"
        "/today — задачи за сегодня"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите текст задачи:")
    return TASK_TEXT


async def add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["text"] = update.message.text
    await update.message.reply_text("Приоритет: низкий / средний / высокий")
    return TASK_PRIORITY


async def add_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    priority = update.message.text.lower()

    if priority not in PRIORITY_MAP:
        await update.message.reply_text("Введите: низкий / средний / высокий")
        return TASK_PRIORITY

    user_id = update.effective_user.id
    text = context.user_data["text"]

    add_task(user_id, text, priority)

    await update.message.reply_text("Задача добавлена ✅")
    return ConversationHandler.END


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = get_tasks(user_id)

    if not tasks:
        await update.message.reply_text("У вас нет задач")
        return

    tasks.sort(key=lambda x: PRIORITY_MAP[x[2]], reverse=True)

    msg = "Ваши задачи:\n\n"
    for i, t in enumerate(tasks, 1):
        msg += f"{i}. {t[1]} ({t[2]})\n"

    await update.message.reply_text(msg)


async def today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")

    tasks = get_tasks(user_id)
    tasks_today = [t for t in tasks if t[3] == today]

    if not tasks_today:
        await update.message.reply_text("Сегодня задач нет")
        return

    msg = "Сегодня:\n\n"
    for t in tasks_today:
        msg += f"- {t[1]} ({t[2]})\n"

    await update.message.reply_text(msg)


# ================= MAIN =================

def main():
    delete_db_on_start()  # убирает старые 13 задач
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_text)],
            TASK_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_priority)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("today", today_tasks))
    app.add_handler(conv)

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
