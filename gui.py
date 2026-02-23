import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Мы будем импортировать функции из main.py (поэтому main.py должен лежать рядом)
import main as core

PROJECT_DIR = Path.cwd()
OUTPUT_DIR = PROJECT_DIR / "output"


def open_folder(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


def try_ocr(image_path: str) -> str:
    """
    OCR: использует core.ocr_image_to_text если он есть в main.py.
    Если в main.py нет OCR-функции (или зависимости не стоят) — покажем понятную ошибку.
    """
    if not hasattr(core, "ocr_image_to_text"):
        raise RuntimeError("OCR не подключён в main.py. (Можно добавить позже.)")
    return core.ocr_image_to_text(image_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Study Pack Assistant")
        self.geometry("900x700")

        core.ensure_dirs() if hasattr(core, "ensure_dirs") else None
        self.cfg = core.load_config() if hasattr(core, "load_config") else {"interests": []}

        self._build_ui()

    def _build_ui(self):
        # Top frame
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="AI-помощник для подготовки к контрольным", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(top, text="Введи предмет, тему и текст — получишь готовый study pack (.md).").pack(anchor="w", pady=(4, 0))

        # Inputs
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="x")

        self.subject_var = tk.StringVar()
        self.topic_var = tk.StringVar()

        ttk.Label(frm, text="Предмет:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.subject_var, width=40).grid(row=0, column=1, sticky="w", padx=8)

        ttk.Label(frm, text="Тема:").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Entry(frm, textvariable=self.topic_var, width=40).grid(row=0, column=3, sticky="w", padx=8)

        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(3, weight=1)

        # Mode
        mode_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        mode_frame.pack(fill="x")

        ttk.Label(mode_frame, text="Режим подготовки:").pack(side="left")
        self.mode_var = tk.StringVar(value="normal")
        ttk.Radiobutton(mode_frame, text="Обычный", variable=self.mode_var, value="normal").pack(side="left", padx=8)
        ttk.Radiobutton(mode_frame, text="Контрольная завтра", variable=self.mode_var, value="tomorrow").pack(side="left", padx=8)
        ttk.Radiobutton(mode_frame, text="Через неделю", variable=self.mode_var, value="week").pack(side="left", padx=8)

        # Interests
        intr_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        intr_frame.pack(fill="x")

        ttk.Label(intr_frame, text="Интересы (через запятую):").pack(side="left")
        self.interests_var = tk.StringVar(value=", ".join(self.cfg.get("interests", [])))
        ttk.Entry(intr_frame, textvariable=self.interests_var, width=60).pack(side="left", padx=8)
        ttk.Button(intr_frame, text="Сохранить", command=self.save_interests).pack(side="left")

        # Text box
        text_frame = ttk.Frame(self, padding=12)
        text_frame.pack(fill="both", expand=True)

        ttk.Label(text_frame, text="Текст параграфа:").pack(anchor="w")
        self.text = tk.Text(text_frame, wrap="word", height=20)
        self.text.pack(fill="both", expand=True, pady=(6, 0))

        # Buttons
        btns = ttk.Frame(self, padding=12)
        btns.pack(fill="x")

        ttk.Button(btns, text="📄 Сгенерировать study pack", command=self.generate).pack(side="left")
        ttk.Button(btns, text="🖼️ Вставить текст из фото (OCR)", command=self.ocr_from_image).pack(side="left", padx=10)
        ttk.Button(btns, text="📂 Открыть папку output", command=lambda: open_folder(OUTPUT_DIR)).pack(side="right")

        # Status
        self.status_var = tk.StringVar(value="Готов к работе.")
        status = ttk.Label(self, textvariable=self.status_var, padding=(12, 0, 12, 12))
        status.pack(fill="x")

    def save_interests(self):
        raw = self.interests_var.get().strip()
        interests = [x.strip() for x in raw.split(",") if x.strip()]
        self.cfg["interests"] = interests[:10]
        if hasattr(core, "save_config"):
            core.save_config(self.cfg)
        self.status_var.set(f"Интересы сохранены: {', '.join(self.cfg['interests'])}" if self.cfg["interests"] else "Интересы очищены.")

    def generate(self):
        subject = self.subject_var.get().strip()
        topic = self.topic_var.get().strip()
        text = self.text.get("1.0", "end").strip()

        if not subject or not topic or not text:
            messagebox.showwarning("Не хватает данных", "Заполни предмет, тему и текст параграфа.")
            return

        # build markdown via core
        try:
            md = core.build_markdown(subject, topic, text, self.mode_var.get(), self.cfg)
        except Exception as e:
            messagebox.showerror("Ошибка генерации", str(e))
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"study_pack_{core.sanitize_filename(topic)}.md"
        out_path = OUTPUT_DIR / filename
        out_path.write_text(md, encoding="utf-8")

        # history if available
        if hasattr(core, "add_to_history"):
            try:
                core.add_to_history(subject, topic, str(out_path))
            except Exception:
                pass

        self.status_var.set(f"Готово! Файл: {out_path}")
        messagebox.showinfo("Готово", f"Создан файл:\n{out_path}")
        open_folder(OUTPUT_DIR)

    def ocr_from_image(self):
        filetypes = [("Images", "*.png *.jpg *.jpeg"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Выбери фото страницы", filetypes=filetypes)
        if not path:
            return

        try:
            text = try_ocr(path)
        except Exception as e:
            messagebox.showerror(
                "OCR не готов",
                "OCR не сработал.\n\n"
                f"Причина: {e}\n\n"
                "Если хочешь OCR — скажи, и я дам точные шаги установки (pytesseract + Tesseract)."
            )
            return

        if not text.strip():
            messagebox.showwarning("Пусто", "Не удалось распознать текст (получилось пусто). Попробуй другое фото.")
            return

        # Put text into text box
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.status_var.set("Текст вставлен из фото (OCR). Проверь и поправь при необходимости.")


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception as e:
        messagebox.showerror("Ошибка запуска", str(e))