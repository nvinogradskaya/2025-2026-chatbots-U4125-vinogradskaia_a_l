import csv
import os
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

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

CSV_FILE = "tasks_data.csv"

TASK_TEXT, TASK_PRIORITY, TASK_TIME = range(3)

PRIORITY_MAP = {
    "высокий": 3,
    "средний": 2,
    "низкий": 1,
}

# ================= CSV =================

def init_csv():
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "text", "priority", "created_at"])


def save_task_to_csv(user_id, text, priority):
    with open(CSV_FILE, "a", encoding="utf-8", newline="\n") as f:
        writer = csv.writer(f)
        writer.writerow([
            user_id,
            text,
            priority,
            datetime.now().strftime("%Y-%m-%d")
        ])


def load_tasks_from_csv():
    tasks = []
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["priority_value"] = PRIORITY_MAP.get(row["priority"], 0)
                tasks.append(row)
    except:
        return []
    return tasks


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это To-Do бот 📝\n\n"
        "/add — добавить задачу\n"
        "/list — список задач\n"
        "/search слово — поиск\n"
        "/today — задачи за сегодня\n"
        "/done — (пока не реализовано)"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/add — добавить задачу\n"
        "/list — список\n"
        "/search текст — поиск\n"
        "/today — задачи за сегодня\n"
        "/done — удалить (в разработке)"
    )


# ================= ADD =================

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите текст задачи:")
    return TASK_TEXT


async def add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["text"] = update.message.text
    await update.message.reply_text("Введите приоритет (низкий / средний / высокий):")
    return TASK_PRIORITY


async def add_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    priority = update.message.text.lower()

    if priority not in PRIORITY_MAP:
        await update.message.reply_text("Ошибка. Введите: низкий / средний / высокий")
        return TASK_PRIORITY

    context.user_data["priority"] = priority
    await update.message.reply_text("Введите время напоминания (в минутах, можно 0):")
    return TASK_TIME


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        int(update.message.text)
    except:
        await update.message.reply_text("Введите число")
        return TASK_TIME

    user_id = update.effective_user.id
    text = context.user_data["text"]
    priority = context.user_data["priority"]

    save_task_to_csv(user_id, text, priority)

    await update.message.reply_text("Задача добавлена ✅")
    return ConversationHandler.END


# ================= LIST =================

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = load_tasks_from_csv()

    tasks = [t for t in tasks if str(t["user_id"]) == str(user_id)]

    if not tasks:
        await update.message.reply_text("У вас пока нет задач")
        return

    tasks = sorted(tasks, key=lambda x: x["priority_value"], reverse=True)

    message = "Ваши задачи:\n\n"
    for i, task in enumerate(tasks, 1):
        message += f"{i}. {task['text']} ({task['priority']})\n"

    await update.message.reply_text(message)


# ================= SEARCH =================

async def search_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Введите текст: /search слово")
        return

    user_id = update.effective_user.id
    keyword = " ".join(context.args).lower()

    tasks = load_tasks_from_csv()
    tasks = [t for t in tasks if str(t["user_id"]) == str(user_id)]

    results = [t for t in tasks if keyword in t["text"].lower()]

    if not results:
        await update.message.reply_text("Ничего не найдено")
        return

    message = "Результаты поиска:\n\n"
    for t in results:
        message += f"- {t['text']} ({t['priority']})\n"

    await update.message.reply_text(message)


# ================= TODAY =================

async def today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")

    tasks = load_tasks_from_csv()
    tasks = [t for t in tasks if str(t["user_id"]) == str(user_id)]

    results = [t for t in tasks if t["created_at"] == today]

    if not results:
        await update.message.reply_text("Сегодня задач нет")
        return

    message = "Задачи на сегодня:\n\n"
    for t in results:
        message += f"- {t['text']} ({t['priority']})\n"

    await update.message.reply_text(message)


# ================= DONE =================

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Удаление задач пока не реализовано"
    )


# ================= MAIN =================

def main():
    # 💥 очищаем старый CSV при каждом деплое
    if os.path.exists(CSV_FILE):
        os.remove(CSV_FILE)

    init_csv()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_text)],
            TASK_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_priority)],
            TASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("search", search_tasks))
    app.add_handler(CommandHandler("today", today_tasks))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(conv_handler)

    print("Bot started...")

    app.run_polling()


if __name__ == "__main__":
    main()
