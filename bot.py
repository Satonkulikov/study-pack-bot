import os
import re
import logging
from pathlib import Path
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm

import main as core  # build_markdown, sanitize_filename


# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("study-pack-bot")


# ---------- States ----------
SUBJECT, TOPIC, TEXT = range(3)

# ---------- Storage ----------
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _user_cfg_path(user_id: int) -> Path:
    return DATA_DIR / f"user_{user_id}.txt"


def load_user_interests(user_id: int) -> list[str]:
    p = _user_cfg_path(user_id)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()][:10]


def save_user_interests(user_id: int, interests: list[str]) -> None:
    _user_cfg_path(user_id).write_text(", ".join(interests[:10]), encoding="utf-8")


def mode_label(mode: str) -> str:
    return {"normal": "Обычный", "tomorrow": "Контрольная завтра", "week": "Через неделю"}.get(mode, mode)


def fmt_label(fmt: str) -> str:
    return {"md": "Markdown (.md)", "pdf": "PDF (.pdf)"}.get(fmt, fmt)


# ---------- PDF helpers ----------
def md_to_text(md: str) -> str:
    text = md
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = text.replace("**", "")
    text = text.replace("* ", "• ")
    return text.strip()


def save_pdf(text: str, out_path: Path, title: str):
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 0.4 * cm)]

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.15 * cm))
            continue
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(safe, styles["BodyText"]))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
        author="Study Pack Bot",
    )
    doc.build(story)


# ---------- Smart block ----------
def smart_block(subject: str, topic: str, text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    hits: list[tuple[int, str]] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 25:
            continue
        score = 0
        if re.search(r"\d", s):
            score += 2
        if re.search(r"=|≈|→|->", s):
            score += 2
        if re.search(r"\b(это|называется|определ|формул|закон|причин|следств|дата)\b", s, re.I):
            score += 1
        if score >= 2:
            hits.append((score, s))

    hits.sort(key=lambda x: x[0], reverse=True)
    top = [h[1] for h in hits[:5]]

    mistakes = [
        "Путают определения и примеры — проговори определение своими словами.",
        "Учат без понимания причин/связей — попробуй объяснить «почему так».",
        "Не умеют применить к задаче/ситуации — реши 2–3 мини-примера.",
    ]

    md = "\n\n## 🧠 Умный блок\n"
    md += "### 5 опорных мыслей\n"
    if top:
        for t in top:
            md += f"- {t}\n"
    else:
        md += "- Выпиши 5 терминов и объясни каждый одной фразой.\n"
        md += "- Найди 2 причины/следствия или 2 главных правила темы.\n"
        md += "- Придумай 2 примера применения.\n"

    md += "\n### Типичные ошибки\n"
    for m in mistakes:
        md += f"- {m}\n"

    md += "\n### 3 вопроса на понимание\n"
    md += "- Объясни тему так, будто учишь друга (1–2 минуты).\n"
    md += "- Приведи свой пример (не из текста) и объясни, почему он подходит.\n"
    md += "- Что изменится, если поменять одно условие/факт?\n"
    return md


# ---------- Keyboards ----------
def main_menu_kb(mode: str, fmt: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧩 Создать study pack", callback_data="menu:study")],
        [
            InlineKeyboardButton(f"⏱ Режим: {mode_label(mode)}", callback_data="menu:mode"),
            InlineKeyboardButton(f"📄 Формат: {fmt_label(fmt)}", callback_data="menu:format"),
        ],
        [
            InlineKeyboardButton("⭐ Интересы", callback_data="menu:interests"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help"),
        ],
    ])


def mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1) Обычный", callback_data="setmode:normal")],
        [InlineKeyboardButton("2) Контрольная завтра", callback_data="setmode:tomorrow")],
        [InlineKeyboardButton("3) Через неделю", callback_data="setmode:week")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
    ])


def format_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Markdown (.md)", callback_data="setfmt:md")],
        [InlineKeyboardButton("🧾 PDF (.pdf)", callback_data="setfmt:pdf")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
    ])


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode", "normal")
    fmt = context.user_data.get("fmt", "md")
    await update.message.reply_text(
        "Привет! Я сделаю study pack по твоему тексту.\nЖми кнопки 👇",
        reply_markup=main_menu_kb(mode, fmt),
    )


async def study_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1) Напиши предмет (например: Физика):")
    return SUBJECT


async def got_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = (update.message.text or "").strip()
    await update.message.reply_text("2) Теперь тема (например: Закон Ома):")
    return TOPIC


async def got_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["topic"] = (update.message.text or "").strip()
    context.user_data["text_parts"] = []
    await update.message.reply_text(
        "3) Вставь текст параграфа.\nМожно несколькими сообщениями.\nКогда закончишь — отправь: DONE"
    )
    return TEXT


async def got_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (update.message.text or "").strip()
    if msg.upper() == "DONE":
        full_text = "\n".join(context.user_data.get("text_parts", [])).strip()
        return await generate_and_send(update, context, full_text)

    if msg:
        context.user_data.setdefault("text_parts", []).append(msg)
    return TEXT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ок, отменил. Чтобы начать снова — /study")
    return ConversationHandler.END


# ---------- Interests capture ----------
async def interests_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_interests"):
        return

    raw = (update.message.text or "").strip()
    interests = [x.strip() for x in raw.split(",") if x.strip()][:10]
    save_user_interests(update.effective_user.id, interests)

    context.user_data["awaiting_interests"] = False

    mode = context.user_data.get("mode", "normal")
    fmt = context.user_data.get("fmt", "md")
    await update.message.reply_text(
        f"✅ Сохранил интересы: {', '.join(interests) if interests else '—'}",
        reply_markup=main_menu_kb(mode, fmt),
    )


# ---------- Callback handlers ----------
async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    mode = context.user_data.get("mode", "normal")
    fmt = context.user_data.get("fmt", "md")

    if q.data == "menu:study":
        # ВАЖНО: это entry_point ConversationHandler (см. main())
        await q.message.reply_text("1) Напиши предмет (например: Физика):")
        return SUBJECT

    if q.data == "menu:mode":
        await q.message.reply_text("Выбери режим:", reply_markup=mode_kb())
        return ConversationHandler.END

    if q.data == "menu:format":
        await q.message.reply_text("Выбери формат:", reply_markup=format_kb())
        return ConversationHandler.END

    if q.data == "menu:interests":
        context.user_data["awaiting_interests"] = True
        await q.message.reply_text("Напиши интересы одной строкой через запятую.\nПример: игры, спорт, машины")
        return ConversationHandler.END

    if q.data == "menu:help":
        await q.message.reply_text(
            "Как пользоваться:\n"
            "1) Нажми «Создать study pack»\n"
            "2) Введи предмет и тему\n"
            "3) Отправь текст (можно несколькими сообщениями)\n"
            "4) Когда закончил — отправь DONE\n\n"
            "Можно и командами: /study",
            reply_markup=main_menu_kb(mode, fmt),
        )
        return ConversationHandler.END

    if q.data == "menu:back":
        await q.message.reply_text("Меню:", reply_markup=main_menu_kb(mode, fmt))
        return ConversationHandler.END


async def on_set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mode = (q.data or "").split(":", 1)[1]
    context.user_data["mode"] = mode
    fmt = context.user_data.get("fmt", "md")
    await q.message.reply_text(f"✅ Режим: {mode_label(mode)}", reply_markup=main_menu_kb(mode, fmt))


async def on_set_fmt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    fmt = (q.data or "").split(":", 1)[1]
    context.user_data["fmt"] = fmt
    mode = context.user_data.get("mode", "normal")
    await q.message.reply_text(f"✅ Формат: {fmt_label(fmt)}", reply_markup=main_menu_kb(mode, fmt))


# ---------- Generate & send ----------
async def generate_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    subject = (context.user_data.get("subject") or "").strip()
    topic = (context.user_data.get("topic") or "").strip()
    if not subject or not topic or not text:
        await update.message.reply_text("Пусто. Начни заново: /study")
        return ConversationHandler.END

    mode = context.user_data.get("mode", "normal")
    fmt = context.user_data.get("fmt", "md")
    interests = load_user_interests(update.effective_user.id)
    cfg = {"interests": interests}

    await update.message.chat.send_action(ChatAction.TYPING)

    md = core.build_markdown(subject, topic, text, mode, cfg)
    md += smart_block(subject, topic, text)

    safe_topic = core.sanitize_filename(topic)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if fmt == "pdf":
        filename = f"study_pack_{safe_topic}_{stamp}.pdf"
        out_path = OUTPUT_DIR / filename
        title = f"Study pack: {subject} — {topic}"
        plain = md_to_text(md)
        save_pdf(plain, out_path, title)
    else:
        filename = f"study_pack_{safe_topic}_{stamp}.md"
        out_path = OUTPUT_DIR / filename
        out_path.write_text(md, encoding="utf-8")

    with open(out_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=filename,
            caption=f"Готово ✅\nРежим: {mode_label(mode)}\nФормат: {fmt_label(fmt)}",
        )

    await update.message.reply_text("Ещё раз?", reply_markup=main_menu_kb(mode, fmt))
    return ConversationHandler.END


# ---------- Error handler ----------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error", exc_info=context.error)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()
    app.add_error_handler(on_error)

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("study", study_cmd),
            CallbackQueryHandler(on_menu, pattern=r"^menu:study$"),
        ],
        states={
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_subject)],
            TOPIC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_topic)],
            TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))

    # Меню/настройки
    app.add_handler(CallbackQueryHandler(on_menu, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(on_set_mode, pattern=r"^setmode:"))
    app.add_handler(CallbackQueryHandler(on_set_fmt, pattern=r"^setfmt:"))

    # Диалог создания study pack
    app.add_handler(conv)

    # Сохранение интересов (срабатывает только когда awaiting_interests=True)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interests_text))

    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()