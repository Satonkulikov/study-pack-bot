from pathlib import Path
import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox

import main as core  # твоя логика генерации из main.py

PROJECT_DIR = Path.cwd()
OUTPUT_DIR = PROJECT_DIR / "output"

def open_path(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass

class StudyPackApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        core.ensure_dirs() if hasattr(core, "ensure_dirs") else None
        self.cfg = core.load_config() if hasattr(core, "load_config") else {"interests": []}
        
        self.last_file = None

        ctk.set_appearance_mode("dark")       # "light" / "dark" / "system"
        ctk.set_default_color_theme("blue")   # "blue" / "green" / "dark-blue"

        self.title("Study Pack Assistant")
        self.geometry("980x720")
        self.minsize(900, 650)

        self.subject_var = ctk.StringVar(value="")
        self.topic_var = ctk.StringVar(value="")
        self.interests_var = ctk.StringVar(value=", ".join(self.cfg.get("interests", [])))
        self.mode_var = ctk.StringVar(value="normal")

        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, corner_radius=16)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ctk.CTkLabel(
            header,
            text="AI-помощник для подготовки к контрольным",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text="Введи предмет, тему и текст — получишь готовый study pack (.md) в папке output.",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # Top inputs
        top = ctk.CTkFrame(self, corner_radius=16)
        top.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(top, text="Предмет").grid(row=0, column=0, padx=(16, 8), pady=(14, 6), sticky="w")
        ctk.CTkEntry(top, textvariable=self.subject_var, height=36).grid(row=1, column=0, padx=(16, 8), pady=(0, 14), sticky="ew")

        ctk.CTkLabel(top, text="Тема").grid(row=0, column=1, padx=(8, 16), pady=(14, 6), sticky="w")
        ctk.CTkEntry(top, textvariable=self.topic_var, height=36).grid(row=1, column=1, padx=(8, 16), pady=(0, 14), sticky="ew")

        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        # Mode + Interests
        mid = ctk.CTkFrame(self, corner_radius=16)
        mid.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(mid, text="Режим").grid(row=0, column=0, padx=(16, 8), pady=(14, 6), sticky="w")

        mode_frame = ctk.CTkFrame(mid, fg_color="transparent")
        mode_frame.grid(row=1, column=0, padx=(16, 8), pady=(0, 14), sticky="w")

        ctk.CTkRadioButton(mode_frame, text="Обычный", variable=self.mode_var, value="normal").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(mode_frame, text="Завтра", variable=self.mode_var, value="tomorrow").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(mode_frame, text="Неделя", variable=self.mode_var, value="week").pack(side="left")

        ctk.CTkLabel(mid, text="Интересы (через запятую)").grid(row=0, column=1, padx=(8, 16), pady=(14, 6), sticky="w")
        ctk.CTkEntry(mid, textvariable=self.interests_var, height=36).grid(row=1, column=1, padx=(8, 16), pady=(0, 14), sticky="ew")

        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)

        # Text area + preview
        body = ctk.CTkFrame(self, corner_radius=16)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        ctk.CTkLabel(body, text="Текст параграфа").grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        ctk.CTkLabel(body, text="Предпросмотр (первые строки)").grid(row=0, column=1, padx=16, pady=(14, 6), sticky="w")

        self.textbox = ctk.CTkTextbox(body, height=420)
        self.textbox.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="nsew")

        self.preview = ctk.CTkTextbox(body, height=420)
        self.preview.grid(row=1, column=1, padx=16, pady=(0, 14), sticky="nsew")
        self.preview.configure(state="disabled")

        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Buttons
        bottom = ctk.CTkFrame(self, corner_radius=16)
        bottom.pack(fill="x", padx=16, pady=(10, 16))
        ctk.CTkButton(
        bottom,
        text="📂 Открыть output",
        height=40,
        fg_color="#444",
        command=lambda: open_path(OUTPUT_DIR)
        ).pack(side="right", padx=(10, 0), pady=14)
        

        ctk.CTkButton(bottom, text="💾 Сохранить интересы", height=40, command=self.save_interests).pack(side="left", padx=16, pady=14)
        ctk.CTkButton(bottom, text="🧹 Очистить", height=40, fg_color="#444", command=self.clear_all).pack(side="left", padx=10, pady=14)
        ctk.CTkButton(bottom, text="👁️ Предпросмотр", height=40, fg_color="#444", command=self.make_preview).pack(side="left", padx=10, pady=14)

        ctk.CTkButton(bottom, text="🚀 Сгенерировать .md", height=40, command=self.generate).pack(side="right", padx=16, pady=14)

        self.status = ctk.CTkLabel(self, text="Готово к работе.", anchor="w")
        self.status.pack(fill="x", padx=18, pady=(0, 10))

    def save_interests(self):
        raw = self.interests_var.get().strip()
        interests = [x.strip() for x in raw.split(",") if x.strip()]
        self.cfg["interests"] = interests[:10]
        if hasattr(core, "save_config"):
            core.save_config(self.cfg)
        self.status.configure(text="Интересы сохранены.")

    def clear_all(self):
        self.subject_var.set("")
        self.topic_var.set("")
        self.textbox.delete("1.0", "end")
        self._set_preview("")
        self.status.configure(text="Очищено.")

    def open_last_file(self):
        if self.last_file and self.last_file.exists():
            open_path(self.last_file)
        else:
            messagebox.showinfo("Файл не найден", "Сначала сгенерируй study pack.")

    def make_preview(self):
        subject = self.subject_var.get().strip()
        topic = self.topic_var.get().strip()
        text = self.textbox.get("1.0", "end").strip()
        if not subject or not topic or not text:
            messagebox.showwarning("Не хватает данных", "Заполни предмет, тему и текст.")
            return
        md = core.build_markdown(subject, topic, text, self.mode_var.get(), self.cfg)
        preview_text = "\n".join(md.splitlines()[:40])
        self._set_preview(preview_text)
        self.status.configure(text="Предпросмотр обновлён.")

    def _set_preview(self, s: str):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", s)
        self.preview.configure(state="disabled")

    def generate(self):
        subject = self.subject_var.get().strip()
        topic = self.topic_var.get().strip()
        text = self.textbox.get("1.0", "end").strip()

        if not subject or not topic or not text:
            messagebox.showwarning("Не хватает данных", "Заполни предмет, тему и текст.")
            return

        try:
            md = core.build_markdown(subject, topic, text, self.mode_var.get(), self.cfg)
        except Exception as e:
            messagebox.showerror("Ошибка генерации", str(e))
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"study_pack_{core.sanitize_filename(topic)}.md"
        out_path = OUTPUT_DIR / filename
        out_path.write_text(md, encoding="utf-8")

        if hasattr(core, "add_to_history"):
            try:
                core.add_to_history(subject, topic, str(out_path))
            except Exception:
                pass

        self._set_preview("\n".join(md.splitlines()[:60]))
        self.status.configure(text=f"Готово! Создано: {out_path}")
        messagebox.showinfo("Готово", f"Файл создан:\n{out_path}")


if __name__ == "__main__":
    app = StudyPackApp()
    app.mainloop()