import re
import json
import textwrap
from datetime import datetime
from pathlib import Path

# ----------------------------
# Paths
# ----------------------------
PROJECT_DIR = Path.cwd()
OUTPUT_DIR = PROJECT_DIR / "output"
HISTORY_PATH = OUTPUT_DIR / "history.json"

APP_DIR = Path.home() / ".study_pack_assistant"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {"interests": []}

STOPWORDS_RU = {
    "и","в","во","не","что","он","на","я","с","со","как","а","то","все","она","так","его","но","да","ты",
    "к","у","же","вы","за","бы","по","только","ее","мне","было","вот","от","меня","еще","нет","о","из",
    "ему","теперь","когда","даже","ну","вдруг","ли","если","уже","или","ни","быть","был","него","до","вас",
    "нибудь","опять","уж","вам","ведь","там","потом","себя","ничего","ей","может","они","тут","где","есть",
    "надо","ней","для","мы","тебя","их","чем","была","сам","чтоб","без","будто","чего","раз","тоже","себе",
    "под","будет","ж","тогда","кто","этот","того","потому","этого","какой","совсем","ним","здесь","этом",
    "один","почти","мой","тем","чтобы","нее","сейчас","были","куда","зачем","всех","никогда","можно","при",
    "наконец","два","об","другой","хоть","после","над","больше","тот","через","эти","нас","про","всего",
    "них","какая","много","разве","три","эту","моя","впрочем","хорошо","свою","этой","перед","иногда","лучше",
    "чуть","том","нельзя","такой","им","более","всегда","конечно","всю","между"
}

# ----------------------------
# Utils
# ----------------------------
def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    ensure_dirs()
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def load_history():
    ensure_dirs()
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(items):
    ensure_dirs()
    HISTORY_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def add_to_history(subject: str, topic: str, filename: str):
    items = load_history()
    items.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "subject": subject,
        "topic": topic,
        "file": filename
    })
    # keep last 200
    items = items[-200:]
    save_history(items)

def sanitize_filename(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zа-я0-9_\-]+", "", s, flags=re.IGNORECASE)
    return s[:80] if s else "topic"

def read_multiline(prompt: str) -> str:
    print(prompt)
    print("(Вставь текст. Заверши ввод строкой: END)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()

def split_sentences(text: str):
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    return [p.strip() for p in parts if p.strip()]

def tokenize(text: str):
    words = re.findall(r"[a-zа-яё0-9]+", text.lower(), flags=re.IGNORECASE)
    return [w for w in words if w and w not in STOPWORDS_RU and len(w) > 2]

def top_keywords(text: str, k=10):
    words = tokenize(text)
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
    return [w for w, _ in ranked[:k]]

def score_sentences(sentences, keywords):
    kw_set = set(keywords)
    scored = []
    for s in sentences:
        toks = tokenize(s)
        score = sum(1 for t in toks if t in kw_set)
        if re.search(r"\d", s):
            score += 1
        if re.search(r"[=×*/+\-]", s):
            score += 1
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for score, s in scored if score > 0] or sentences[:]

def extract_key_facts(text: str, max_facts=12):
    sentences = split_sentences(text)
    if not sentences:
        return []
    keywords = top_keywords(text, k=12)
    ranked = score_sentences(sentences, keywords)
    facts, seen = [], set()
    for s in ranked:
        norm = re.sub(r"\s+", " ", s.lower())
        if norm in seen:
            continue
        seen.add(norm)
        facts.append(s)
        if len(facts) >= max_facts:
            break
    return facts

# ----------------------------
# Personalization
# ----------------------------
def setup_interests(cfg: dict):
    print("Персонализация")
    raw = input("Что тебе интересно? (например: спорт, игры, машины, музыка): ").strip()
    interests = [x.strip() for x in re.split(r"[,\|;/]+", raw) if x.strip()]
    cfg["interests"] = interests[:10]
    save_config(cfg)
    print(f"Сохранено интересов: {len(cfg['interests'])}")

def interest_examples(subject: str, topic: str, interests: list[str]):
    if not interests:
        return ""

    subject_l = subject.lower()
    is_mathlike = any(x in subject_l for x in ["матем", "алгеб", "геом", "физ", "хим", "информ"])
    is_human = any(x in subject_l for x in ["истор", "литер", "общест", "геогр", "биол", "рус", "англ"])

    blocks = []
    for intr in interests[:3]:
        if is_mathlike:
            blocks.append(f"- **{intr}**: придумай мини-задачу по теме «{topic}» на примере {intr} и реши её.")
        elif is_human:
            blocks.append(f"- **{intr}**: найди аналогию к теме «{topic}» в {intr} и объясни сходство/различия.")
        else:
            blocks.append(f"- **{intr}**: объясни тему «{topic}» через пример из {intr} (5–7 предложений).")

    return "\n".join(blocks)

# ----------------------------
# Plan + Tasks
# ----------------------------
def choose_time_mode():
    print("\nВыбери режим подготовки:")
    print("1) Обычный (20–30 минут)")
    print("2) Контрольная завтра (быстро и по сути)")
    print("3) Контрольная через неделю (чуть глубже)")
    choice = input("Введи 1/2/3: ").strip()
    if choice == "2":
        return "tomorrow"
    if choice == "3":
        return "week"
    return "normal"

def make_plan(subject: str, topic: str, text: str, time_mode: str):
    subject_l = subject.strip().lower()
    is_mathlike = any(x in subject_l for x in ["матем", "алгеб", "геом", "физ", "хим", "информ"])
    is_human = any(x in subject_l for x in ["истор", "литер", "общест", "геогр", "биол", "рус", "англ"])

    if time_mode == "tomorrow":
        t_label, depth = "20–30 минут", "максимально быстро"
    elif time_mode == "week":
        t_label, depth = "35–50 минут", "чуть глубже"
    else:
        t_label, depth = "20–30 минут", "оптимально"

    keywords = top_keywords(text, k=8)
    kw_line = ", ".join(keywords) if keywords else "—"

    steps = []
    steps.append(f"**Цель:** за {t_label} собрать тему «{topic}» ({depth}).")
    steps.append(f"**Ключевые слова:** {kw_line}")
    steps.append("1) **Прочитай (3–5 мин):** отметь 5–7 ключевых терминов/идей.")
    steps.append("2) **Пойми (5–7 мин):** что это такое, от чего зависит, почему так.")
    steps.append("3) **Запомни (5–7 мин):** выпиши 5–8 тезисов + 3 определения.")
    if is_mathlike:
        steps.append("4) **Формулы/правила (5–8 мин):** выпиши и подпиши обозначения.")
        steps.append("5) **Практика (5–10 мин):** реши 2–4 типовых задания (простые → средние).")
        if time_mode == "week":
            steps.append("6) **Закрепление (5–10 мин):** ещё 2 задачи другого типа + повтор карточек через день.")
    elif is_human:
        steps.append("4) **Структура (5–8 мин):** причины → ход/события → итоги/вывод.")
        steps.append("5) **Самопроверка (5–10 мин):** перескажи по плану 1–2 минуты + тест.")
        if time_mode == "week":
            steps.append("6) **Закрепление (5–10 мин):** сделай 5 своих вопросов и ответь без текста.")
    else:
        steps.append("4) **Схема (5–8 мин):** таблица/схема: понятие → признаки → примеры.")
        steps.append("5) **Практика (5–10 мин):** 2–3 задания из конца параграфа.")
        if time_mode == "week":
            steps.append("6) **Закрепление (5–10 мин):** повтор карточек через день + тест ещё раз.")

    return "\n".join(f"- {s}" for s in steps)

def build_typical_tasks(subject: str, topic: str, text: str):
    subject_l = subject.lower()
    is_mathlike = any(x in subject_l for x in ["матем", "алгеб", "геом", "физ", "хим", "информ"])
    is_human = any(x in subject_l for x in ["истор", "литер", "общест", "геогр", "биол", "рус", "англ"])

    kws = top_keywords(text, k=6)
    kw_hint = ", ".join(kws) if kws else topic

    if is_mathlike:
        return [
            f"Подставь числа в формулу/правило по теме «{topic}» (1–2 задания на прямую подстановку).",
            "Задача «на изменение параметра»: что станет с результатом, если увеличить/уменьшить одну величину?",
            "Задача с единицами измерения: переведи величины и проверь размерность ответа.",
            f"Найди/составь 2 задачи из учебника по ключевым словам: {kw_hint}."
        ]
    if is_human:
        return [
            f"Составь мини-план по теме «{topic}» (3–5 пунктов) и перескажи по нему.",
            "Выдели 3 причины и 3 последствия (если тема про событие/процесс).",
            "Сделай таблицу: «термин → объяснение → пример».",
            f"Подготовь 5 дат/фактов по ключевым словам: {kw_hint}."
        ]
    return [
        f"Сделай схему: «главное понятие → признаки → примеры» по теме «{topic}».",
        "Ответь письменно на 3 вопроса из конца параграфа (или придумай свои).",
        "Составь 5 утверждений: 3 верных и 2 неверных — и проверь себя.",
        f"Проверь, понимаешь ли слова/термины: {kw_hint}."
    ]

# ----------------------------
# Flashcards
# ----------------------------
def build_flashcards(subject: str, topic: str, text: str, n=10):
    facts = extract_key_facts(text, max_facts=max(16, n))
    cards = []
    for s in facts:
        if len(cards) >= n:
            break
        if re.search(r"=", s):
            cards.append(("Как записывается ключевая формула/соотношение?", s))
        elif re.search(r"\b\d{4}\b|\b\d+\b", s):
            cards.append(("Какой важный факт/число/дата по теме?", s))
        elif "— это" in s.lower() or "называют" in s.lower():
            cards.append(("Дай определение:", s))
        else:
            cards.append(("Что важно помнить по теме?", s))

    while len(cards) < n:
        cards.append(("Назови 1 ключевую идею темы.", "Перечитай план и сформулируй главный тезис в 1–2 предложениях."))

    return cards

# ----------------------------
# Better quiz with A/B/C/D
# ----------------------------
def make_distractors(correct: str, pool: list[str]) -> list[str]:
    # pick 3 "wrong but plausible" answers from pool
    wrong = []
    for s in pool:
        if s == correct:
            continue
        if len(wrong) >= 3:
            break
        wrong.append(s)
    # if not enough, add generic distractors
    while len(wrong) < 3:
        wrong.append("Неверный вариант (проверь по тексту).")
    return wrong[:3]

def build_quiz_mcq(text: str, n=8):
    facts = extract_key_facts(text, max_facts=18)
    if not facts:
        return [], []

    # Answer pool: shorten facts so options look clean
    pool = []
    for f in facts:
        short = f.strip()
        short = re.sub(r"\s+", " ", short)
        pool.append(short[:160] + ("…" if len(short) > 160 else ""))

    questions = []
    key = []

    for i in range(min(n, len(pool))):
        correct = pool[i]
        # question type heuristics
        if re.search(r"=", correct):
            q = "Выбери вариант, где записана формула/соотношение из текста:"
        elif re.search(r"\b\d{4}\b", correct):
            q = "Выбери вариант, где указан важный год/дата/факт из текста:"
        else:
            q = "Выбери вариант, который соответствует утверждению из параграфа:"

        wrong = make_distractors(correct, pool[i+1:] + pool[:i])
        options = [correct] + wrong

        # shuffle without random (deterministic): rotate by index
        # ensures correct not always A
        rot = i % 4
        options = options[rot:] + options[:rot]
        letters = ["A", "B", "C", "D"]

        correct_letter = letters[options.index(correct)]
        questions.append((q, list(zip(letters, options))))
        key.append(correct_letter)

    # pad to n if needed
    while len(questions) < n:
        q = "Выбери наиболее верный вывод по теме:"
        opts = [("A", "Верно (проверь по тексту)."),
                ("B", "Неверно (проверь по тексту)."),
                ("C", "Частично верно (проверь по тексту)."),
                ("D", "Не относится к теме.")]
        questions.append((q, opts))
        key.append("A")

    return questions, key

def build_check_yourself(topic: str):
    return [
        f"Объясни тему «{topic}» за 60 секунд (без подсказок).",
        "Приведи 2 примера и 1 контрпример (когда правило/идея не подходит).",
        "Если изменить одно условие, что поменяется и почему?",
    ]

# ----------------------------
# Markdown
# ----------------------------
def build_markdown(subject: str, topic: str, text: str, time_mode: str, cfg: dict):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    plan = make_plan(subject, topic, text, time_mode)
    cards = build_flashcards(subject, topic, text, n=10)
    mcq, mcq_key = build_quiz_mcq(text, n=8)
    check = build_check_yourself(topic)
    tasks = build_typical_tasks(subject, topic, text)

    intr = interest_examples(subject, topic, cfg.get("interests", []))

    mode_label = "Обычный"
    if time_mode == "tomorrow":
        mode_label = "Контрольная завтра"
    elif time_mode == "week":
        mode_label = "Контрольная через неделю"

    md = []
    md.append(f"# Study Pack: {topic}\n")
    md.append(f"**Предмет:** {subject}")
    md.append(f"**Дата:** {now}")
    md.append(f"**Режим:** {mode_label}\n")

    md.append("## 1) План подготовки")
    md.append(plan + "\n")

    md.append("## 2) Карточки для повторения (10)")
    for i, (q, a) in enumerate(cards, 1):
        md.append(f"{i}. **{q}** → {a}")
    md.append("")

    md.append("## 3) Мини-тест (A/B/C/D)")
    for i, (q, opts) in enumerate(mcq, 1):
        md.append(f"{i}. {q}")
        for letter, opt in opts:
            md.append(f"   - {letter}) {opt}")
    md.append("\n### Ключ ответов")
    md.append(", ".join(f"{i+1}{mcq_key[i]}" for i in range(len(mcq_key))))
    md.append("")

    md.append("## 4) Типовые задания (что прорешать/сделать)")
    for i, t in enumerate(tasks, 1):
        md.append(f"{i}. {t}")
    md.append("")

    md.append("## 5) Проверь себя")
    for i, q in enumerate(check, 1):
        md.append(f"{i}. {q}")
    md.append("")

    if intr:
        md.append("## 6) Примеры на твоих интересах")
        md.append(intr + "\n")
        md.append("## 7) Исходный текст (для сверки)")
    else:
        md.append("## 6) Исходный текст (для сверки)")

    md.append("\n> Ниже — текст, который ты вставил(а).\n")
    md.append("```")
    md.append(text.strip())
    md.append("```")
    md.append("")

    return "\n".join(md)

# ----------------------------
# Main
# ----------------------------
def main():
    ensure_dirs()
    cfg = load_config()

    print("=== AI-помощник для подготовки к контрольным ===")
    print("Подсказка: в любой момент можно вставить текст и закончить строкой END.\n")

    if not cfg.get("interests"):
        ans = input("Хочешь включить персонализацию по интересам? (y/n): ").strip().lower()
        if ans in {"y", "yes", "д", "да"}:
            setup_interests(cfg)

    ans_photo = input("Будем вводить текст вручную или по фото? (1=вручную, 2=фото): ").strip()

    subject = input("1) Предмет: ").strip()
    topic = input("2) Тема: ").strip()

    if ans_photo == "2":
        print("\nOCR-режим оставим следующим апдейтом (чтобы без лишних установок).")
        print("Сейчас перейдём на ручной ввод.\n")

    text = read_multiline("3) Вставь текст параграфа:")
    if not text.strip():
        print("Пустой текст. Нечего собирать. Завершение.")
        return

    time_mode = choose_time_mode()
    md = build_markdown(subject, topic, text, time_mode, cfg)

    filename = f"study_pack_{sanitize_filename(topic)}.md"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(md, encoding="utf-8")

    add_to_history(subject, topic, str(out_path))

    print("\n✅ Готово!")
    print(f"Файл создан: {out_path}")
    print("История: output/history.json\n")

    print("--- Короткий предпросмотр ---")
    print(textwrap.shorten(md.replace("\n", " "), width=650, placeholder=" ..."))

if __name__ == "__main__":
    main()