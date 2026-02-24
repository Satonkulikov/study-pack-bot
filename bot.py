import os
import re
import asyncio
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

import main as core  # твой генератор (build_markdown, sanitize_filename и т.д.)

# Состояния диалога
SUBJECT, TOPIC, TEXT = range(3)

DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)

def user_cfg_path(user_id: int) -> Path:
    return DATA_DIR / f"user_{user_id}.txt"

def load_user_interests(user_id: int) -> list[str]:
    p = user_cfg_path(user_id)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()][:10]

def save_user_interests(user_id: int, interests: list[str]):
    user_cfg_path(user_id).write_text(", ".join(interests[:10]), encoding="utf-8")

def normalize_mode(text: str) -> str:
    t = text.strip().lower()
    if t in {"1", "обычный", "normal"}:
        return "normal"
    if t in {"2", "завтра", "tomorrow"}:
        return "tomorrow"
    if t in {"3", "неделя", "week"}:
        return "week"
    return "normal"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я сделаю study boost.\n\n"
        "Команды:\n"
        "/study — создать study boost\n"
        "/interests игры, спорт, машины — сохранить интересы\n"
        "/mode 1|2|3 — режим (1 обычный, 2 завтра, 3 неделя)\n"
        "/cancel — отмена"
    )

async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw = update.message.text.replace("/interests", "", 1).strip()
    if not raw:
        await update.message.reply_text("Напиши так: /interests игры, спорт, машины")
        return
    interests = [x.strip() for x in re.split(r"[,\|;/]+", raw) if x.strip()]
    save_user_interests(user_id, interests)
    await update.message.reply_text(f"Сохранил интересы: {', '.join(interests[:10])}")

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.replace("/mode", "", 1).strip()
    mode = normalize_mode(raw)
    context.user_data["mode"] = mode
    label = {"normal":"Обычный", "tomorrow":"Завтра", "week":"Неделя"}[mode]
    await update.message.reply_text(f"Режим установлен: {label}")

async def study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1) Напиши предмет (например: Физика):")
    return SUBJECT

async def got_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text("2) Теперь тема (например: Закон Ома):")
    return TOPIC

async def got_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["topic"] = update.message.text.strip()
    await update.message.reply_text(
        "3) Вставь текст параграфа одним сообщением.\n"
        "Можно большим куском."
    )
    return TEXT

async def got_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = context.user_data.get("subject", "").strip()
    topic = context.user_data.get("topic", "").strip()
    text = update.message.text.strip()

    if not subject or not topic or not text:
        await update.message.reply_text("Что-то пустое. Давай заново: /study")
        return ConversationHandler.END

    mode = context.user_data.get("mode", "normal")
    interests = load_user_interests(user_id)
    cfg = {"interests": interests}

    await update.message.chat.send_action(action=ChatAction.TYPING)

    md = core.build_markdown(subject, topic, text, mode, cfg)

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    filename = f"study_pack_{core.sanitize_filename(topic)}.md"
    out_path = out_dir / filename
    out_path.write_text(md, encoding="utf-8")

    # Отправляем файл
    await update.message.reply_document(
        document=open(out_path, "rb"),
        filename=filename,
        caption=f"Готово ✅\nПредмет: {subject}\nТема: {topic}"
    )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ок, отменил. Чтобы начать снова: /study")
    return ConversationHandler.END

def main():
    token = os.getenv("BOT_TOKEN")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("study", study)],
        states={
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_subject)],
            TOPIC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_topic)],
            TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("interests", set_interests))
    app.add_handler(CommandHandler("mode", set_mode))
    app.add_handler(conv)
    
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    app.run_polling()

if __name__ == "__main__":
    main()