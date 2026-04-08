import json
import os
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

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Файл с задачами
TASKS_FILE = "tasks.json"

# Состояния для диалога
TASK_TEXT, TASK_PRIORITY, TASK_TIME = range(3)

# Приоритеты
PRIORITY_MAP = {
    "высокий": 3,
    "средний": 2,
    "низкий": 1,
}


# ===================== Работа с файлом =====================

def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ===================== Команды =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я To-Do бот.\n\n"
        "Команды:\n"
        "/add — добавить задачу\n"
        "/list — список задач\n"
        "/done — завершить задачу\n"
        "/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться ботом:\n"
        "/add — добавить задачу\n"
        "/list — посмотреть задачи\n"
        "/done — удалить задачу по номеру"
    )


# ===================== Добавление задачи =====================

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
        await update.message.reply_text("Неверный приоритет. Введите: низкий / средний / высокий")
        return TASK_PRIORITY

    context.user_data["priority"] = priority
    await update.message.reply_text("Введите время напоминания в минутах (или 0):")
    return TASK_TIME


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(update.message.text)
    except:
        await update.message.reply_text("Введите число (например 10)")
        return TASK_TIME

    task = {
        "text": context.user_data["text"],
        "priority": context.user_data["priority"],
        "priority_value": PRIORITY_MAP[context.user_data["priority"]],
        "reminder": minutes,
        "user_id": update.effective_chat.id,
    }

    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)

    # Планирование напоминания
    if minutes > 0:
        context.job_queue.run_once(
            send_reminder,
            when=minutes * 60,
            data=task,
        )

    await update.message.reply_text("Задача добавлена!")
    return ConversationHandler.END


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    task = context.job.data
    await context.bot.send_message(
        chat_id=task["user_id"],
        text=f"Напоминание: {task['text']}"
    )


# ===================== Список задач =====================

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = load_tasks()

    if not tasks:
        await update.message.reply_text("Список задач пуст")
        return

    # сортировка по приоритету
    tasks = sorted(tasks, key=lambda x: x["priority_value"], reverse=True)

    message = "Ваши задачи:\n\n"
    for i, task in enumerate(tasks, start=1):
        message += f"{i}. {task['text']} ({task['priority']})\n"

    await update.message.reply_text(message)


# ===================== Удаление задачи =====================

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        index = int(context.args[0]) - 1
    except:
        await update.message.reply_text("Использование: /done НОМЕР")
        return

    tasks = load_tasks()

    if index < 0 or index >= len(tasks):
        await update.message.reply_text("Неверный номер задачи")
        return

    removed = tasks.pop(index)
    save_tasks(tasks)

    await update.message.reply_text(f"Удалена задача: {removed['text']}")


# ===================== MAIN =====================

def main():
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
    app.add_handler(CommandHandler("done", done))
    app.add_handler(conv_handler)

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()