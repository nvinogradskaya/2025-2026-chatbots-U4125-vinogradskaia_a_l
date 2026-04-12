import os
import sqlite3
from datetime import datetime, time

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
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


def get_tasks(user_id, mode="all", tag=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    query = """
        SELECT id, text, priority, tag, reminder_time, is_done, created_at
        FROM tasks
        WHERE user_id = ? AND is_deleted = 0
    """

    cur.execute(query, (user_id,))
    rows = cur.fetchall()
    conn.close()

    if mode == "active":
        rows = [r for r in rows if r[5] == 0]
    elif mode == "done":
        rows = [r for r in rows if r[5] == 1]

    if tag:
        rows = [r for r in rows if r[3] == tag]

    return rows


def mark_done(task_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        UPDATE tasks SET is_done = 1
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()


def delete_task(task_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        UPDATE tasks SET is_deleted = 1
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()


# ================= UI =================

def task_keyboard(task_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✔ Done", callback_data=f"done:{task_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"del:{task_id}")
        ]
    ])


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 To-Do бот\n\n"
        "/add — добавить задачу\n"
        "/list [active/done/tag]\n"
        "/stats — статистика\n"
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
    await update.message.reply_text("Время напоминания HH:MM или -")
    return TASK_TIME


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["time"] = None if text == "-" else text

    await update.message.reply_text(f"Тег {TAGS}")
    return TASK_TAG


async def add_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.lower()

    if tag not in TAGS:
        await update.message.reply_text(f"Выбери из {TAGS}")
        return TASK_TAG

    add_task(
        update.effective_user.id,
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

    mode = "all"
    tag = None

    if context.args:
        if context.args[0] in ["active", "done"]:
            mode = context.args[0]
        else:
            tag = context.args[0]

    tasks = get_tasks(user_id, mode=mode, tag=tag)

    if not tasks:
        await update.message.reply_text("Нет задач")
        return

    msg = "📋 Задачи:\n\n"

    for t in tasks:
        status = "✅" if t[5] else "⏳"
        msg += f"{t[0]}. {t[1]} [{t[2]} | {t[3]}] {status}\n"

        await update.message.reply_text(
            f"{t[1]} ({t[2]})",
            reply_markup=task_keyboard(t[0])
        )


# ================= INLINE BUTTONS =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, task_id = query.data.split(":")
    user_id = query.from_user.id

    if action == "done":
        mark_done(task_id, user_id)
        await query.edit_message_text("✔ Выполнено")

    elif action == "del":
        delete_task(task_id, user_id)
        await query.edit_message_text("🗑 Удалено")


# ================= STATS =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = get_tasks(update.effective_user.id)

    total = len(tasks)
    done = sum(1 for t in tasks if t[5])

    msg = f"""
📊 Статистика

Всего: {total}
Выполнено: {done}
Активных: {total - done}
"""

    if total > 0 and done / total > 0.6:
        msg += "\n🔥 Ты молодец!"

    await update.message.reply_text(msg)


# ================= REMINDERS =================

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%H:%M")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, text FROM tasks
        WHERE reminder_time = ? AND is_done = 0 AND is_deleted = 0
    """, (now,))

    rows = cur.fetchall()
    conn.close()

    for user_id, text in rows:
        await context.bot.send_message(user_id, f"⏰ Напоминание: {text}")


# ================= HELP =================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 To-Do бот — инструкция\n\n"
        
        "📌 Основные команды:\n"
        "/add — создать задачу (пошагово)\n"
        "/list — все задачи\n"
        "/list active — только активные задачи\n"
        "/list done — выполненные задачи\n"
        "/list <тег> — фильтр по тегу\n"
        "/stats — статистика по задачам\n\n"
        
        "📌 Работа с задачами:\n"
        "После /list у каждой задачи есть кнопки:\n"
        "✔ Done — отметить выполненной\n"
        "🗑 Delete — удалить задачу\n\n"
        
        "📌 При создании задачи (/add):\n"
        "1) текст задачи\n"
        "2) приоритет: низкий / средний / высокий\n"
        "3) время напоминания: HH:MM или -\n"
        "4) тег:\n"
        "   работа / учеба / хобби / здоровье / дом / прочее\n\n"
        
        "📌 Напоминания:\n"
        "Если указано время (HH:MM), бот пришлёт уведомление в этот момент\n\n"
        
        "📌 Статистика (/stats):\n"
        "- всего задач\n"
        "- выполнено\n"
        "- активные\n"
        "- процент продуктивности\n\n"
        
        "🔥 Если выполняешь >60% задач — бот тебя хвалит\n"
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
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(button_handler))

    # scheduler (каждую минуту проверяем напоминания)
    app.job_queue.run_repeating(reminder_job, interval=60, first=10)

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
