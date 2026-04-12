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

TASK_TEXT, TASK_PRIORITY, TASK_TIME, TASK_TAG = range(4)

PRIORITY_MAP = {
    "высокий": 3,
    "средний": 2,
    "низкий": 1,
}

TAGS = ["работа", "учеба", "хобби", "здоровье", "дом", "прочее"]


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
            tag TEXT DEFAULT 'прочее',
            reminder_time TEXT DEFAULT NULL,
            is_done INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_task(user_id, text, priority, tag, reminder_time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO tasks (user_id, text, priority, tag, reminder_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, text, priority, tag, reminder_time, datetime.now().strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()


def get_tasks(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, text, priority, tag, reminder_time, is_done, created_at
        FROM tasks
        WHERE user_id = ? AND is_deleted = 0
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return rows


def mark_done(task_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        UPDATE tasks
        SET is_done = 1
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()


def delete_task(task_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        UPDATE tasks
        SET is_deleted = 1
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 To-Do бот\n\n"
        "/add — добавить задачу\n"
        "/list — список задач\n"
        "/done <id> — отметить выполненной\n"
        "/delete <id> — удалить задачу\n"
        "/stats — статистика\n"
        "/today — задачи за сегодня\n"
        "/help — помощь"
    )


# ================= ADD FLOW =================

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

    context.user_data["priority"] = priority
    await update.message.reply_text("Время напоминания (HH:MM или -):")
    return TASK_TIME


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["time"] = None if text == "-" else text

    await update.message.reply_text(f"Тег {TAGS}:")
    return TASK_TAG


async def add_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.lower()

    if tag not in TAGS:
        await update.message.reply_text(f"Выбери из {TAGS}")
        return TASK_TAG

    user_id = update.effective_user.id

    add_task(
        user_id,
        context.user_data["text"],
        context.user_data["priority"],
        tag,
        context.user_data["time"]
    )

    await update.message.reply_text("Задача добавлена ✅")
    return ConversationHandler.END


# ================= LIST =================

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = get_tasks(user_id)

    if not tasks:
        await update.message.reply_text("У вас нет задач")
        return

    msg = "📋 Ваши задачи:\n\n"

    for t in tasks:
        status = "✅" if t[5] else "⏳"
        msg += f"{t[0]}. {t[1]} [{t[2]} | {t[3]}] {t[4] or ''} {status}\n"

    await update.message.reply_text(msg)


# ================= DONE =================

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /done <id>")
        return

    task_id = int(context.args[0])
    user_id = update.effective_user.id

    mark_done(task_id, user_id)

    await update.message.reply_text("Задача выполнена 🎉")


# ================= DELETE =================

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /delete <id>")
        return

    task_id = int(context.args[0])
    user_id = update.effective_user.id

    delete_task(task_id, user_id)

    await update.message.reply_text("Задача удалена 🗑")


# ================= TODAY =================

async def today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")

    tasks = get_tasks(user_id)
    tasks_today = [t for t in tasks if t[6] == today]

    if not tasks_today:
        await update.message.reply_text("Сегодня задач нет")
        return

    msg = "📅 Сегодня:\n\n"
    for t in tasks_today:
        msg += f"- {t[1]} ({t[2]})\n"

    await update.message.reply_text(msg)


# ================= STATS =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = get_tasks(user_id)

    total = len(tasks)
    done_count = sum(1 for t in tasks if t[5])
    not_done = total - done_count

    priorities = {"высокий":0, "средний":0, "низкий":0}
    for t in tasks:
        priorities[t[2]] += 1

    msg = (
        "📊 Статистика\n\n"
        f"Всего задач: {total}\n"
        f"Выполнено: {done_count}\n"
        f"Активных: {not_done}\n\n"
        f"Приоритеты:\n"
        f"- высокий: {priorities['высокий']}\n"
        f"- средний: {priorities['средний']}\n"
        f"- низкий: {priorities['низкий']}\n\n"
    )

    if done_count / total > 0.6:
        msg += "Ты молодец, так держать 🔥"

    await update.message.reply_text(msg)


# ================= HELP =================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 To-Do бот\n\n"
        "/add — добавить задачу\n"
        "/list — список\n"
        "/done <id> — выполнить задачу\n"
        "/delete <id> — удалить задачу\n"
        "/today — задачи за сегодня\n"
        "/stats — статистика\n\n"
        "Теги: работа, учеба, хобби, здоровье, дом, прочее\n"
        "Приоритет: высокий / средний / низкий\n"
        "Время: HH:MM (или -)"
    )


# ================= MAIN =================

def main():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_text)],
            TASK_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_priority)],
            TASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
            TASK_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tag)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("today", today_tasks))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv)

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
