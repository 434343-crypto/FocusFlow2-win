# -*- coding: utf-8 -*-
"""
FocusFlow — Windows desktop version.
Single-file Python app using only the standard library (tkinter, winsound).
Build to a real .exe with PyInstaller (see README.md).

Behaviour mirrors the original web app / Android app:
- Same schedule algorithm (105-min study blocks + merged 15-min break,
  Lunch at 13:00, Dinner at 21:00).
- When a session/break starts, a real full-screen, always-on-top alarm
  window appears that cannot be closed (Alt+F4 / X button disabled) until
  a random math question from the same 100-question bank is answered
  correctly.
- Runs quietly in the main window; settings (enabled/disabled sessions,
  renamed study blocks) are saved to a JSON file next to the exe so they
  persist between runs.
"""

import json
import os
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from datetime import datetime

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False  # allows the script to at least run/test on non-Windows

# ---------------------------------------------------------------------------
# Math question bank (identical to the original HTML / Android versions)
# ---------------------------------------------------------------------------
MATH_BANK = [
    ("915 - 898 = ?", 17),
    ("120 x 32 = ?", 3840),
    ("454 - 192 = ?", 262),
    ("480 / 15 = ?", 32),
    ("544 / 32 = ?", 17),
    ("840 / 21 = ?", 40),
    ("149 + 174 = ?", 323),
    ("570 - 253 = ?", 317),
    ("777 - 161 = ?", 616),
    ("788 - 407 = ?", 381),
    ("342 x 33 = ?", 11286),
    ("326 + 147 = ?", 473),
    ("759 / 33 = ?", 23),
    ("196 + 474 = ?", 670),
    ("676 - 564 = ?", 112),
    ("900 / 30 = ?", 30),
    ("506 + 150 = ?", 656),
    ("275 / 11 = ?", 25),
    ("534 + 160 = ?", 694),
    ("226 x 23 = ?", 5198),
    ("277 x 11 = ?", 3047),
    ("888 / 24 = ?", 37),
    ("784 - 754 = ?", 30),
    ("252 / 18 = ?", 14),
    ("972 / 36 = ?", 27),
    ("392 - 290 = ?", 102),
    ("336 x 22 = ?", 7392),
    ("288 / 12 = ?", 24),
    ("299 - 240 = ?", 59),
    ("898 - 285 = ?", 613),
    ("551 - 473 = ?", 78),
    ("320 - 231 = ?", 89),
    ("159 x 26 = ?", 4134),
    ("305 x 28 = ?", 8540),
    ("247 x 15 = ?", 3705),
    ("653 + 220 = ?", 873),
    ("354 x 29 = ?", 10266),
    ("345 / 15 = ?", 23),
    ("588 / 28 = ?", 21),
    ("147 x 19 = ?", 2793),
    ("696 + 159 = ?", 855),
    ("737 - 606 = ?", 131),
    ("722 / 19 = ?", 38),
    ("700 - 531 = ?", 169),
    ("506 / 23 = ?", 22),
    ("637 - 421 = ?", 216),
    ("279 x 30 = ?", 8370),
    ("195 / 13 = ?", 15),
    ("684 + 415 = ?", 1099),
    ("385 x 29 = ?", 11165),
    ("288 / 16 = ?", 18),
    ("504 + 766 = ?", 1270),
    ("708 - 644 = ?", 64),
    ("297 x 39 = ?", 11583),
    ("185 x 25 = ?", 4625),
    ("260 x 21 = ?", 5460),
    ("929 - 164 = ?", 765),
    ("690 + 699 = ?", 1389),
    ("300 x 40 = ?", 12000),
    ("529 + 247 = ?", 776),
    ("975 - 450 = ?", 525),
    ("200 / 20 = ?", 10),
    ("682 / 22 = ?", 31),
    ("192 + 664 = ?", 856),
    ("449 - 141 = ?", 308),
    ("186 x 30 = ?", 5580),
    ("395 x 32 = ?", 12640),
    ("133 x 12 = ?", 1596),
    ("328 x 20 = ?", 6560),
    ("840 / 30 = ?", 28),
    ("696 + 163 = ?", 859),
    ("258 x 31 = ?", 7998),
    ("350 / 14 = ?", 25),
    ("823 - 174 = ?", 649),
    ("833 - 310 = ?", 523),
    ("255 / 15 = ?", 17),
    ("355 - 338 = ?", 17),
    ("988 / 38 = ?", 26),
    ("171 + 346 = ?", 517),
    ("940 + 648 = ?", 1588),
    ("504 / 28 = ?", 18),
    ("628 - 268 = ?", 360),
    ("946 + 679 = ?", 1625),
    ("130 x 17 = ?", 2210),
    ("670 + 979 = ?", 1649),
    ("354 x 13 = ?", 4602),
    ("431 + 254 = ?", 685),
    ("226 + 328 = ?", 554),
    ("619 + 319 = ?", 938),
    ("540 / 15 = ?", 36),
    ("659 - 394 = ?", 265),
    ("745 + 742 = ?", 1487),
    ("236 + 396 = ?", 632),
    ("333 x 13 = ?", 4329),
    ("305 - 248 = ?", 57),
    ("544 + 528 = ?", 1072),
    ("673 + 935 = ?", 1608),
    ("138 + 188 = ?", 326),
    ("139 x 35 = ?", 4865),
    ("858 / 39 = ?", 22),
]

APPDATA_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "FocusFlow", "focusflow_data.json"
)

# ---------------------------------------------------------------------------
# Schedule generation — exact port of the original JS generateSchedule()
# ---------------------------------------------------------------------------
def generate_schedule():
    sessions = []
    study_counter = 1
    t = 0
    meals = [("Lunch", 780, 45), ("Dinner", 1260, 30)]

    while t < 1440:
        meal_hit = False
        for name, start, dur in meals:
            if t == start:
                sessions.append({
                    "id": f"m{t}", "type": "meal", "name": name,
                    "start": t, "end": t + dur, "enabled": True,
                    "breakStart": None, "breakMin": 0,
                })
                t += dur
                meal_hit = True
                break
        if meal_hit:
            continue

        nxt = 1440
        for name, start, dur in meals:
            if start > t:
                nxt = min(nxt, start)

        study_start = t
        study_dur = min(105, nxt - t)
        if study_dur > 0:
            sessions.append({
                "id": f"s{t}", "type": "study", "name": f"Study {study_counter}",
                "start": t, "end": t + study_dur, "enabled": True,
                "breakStart": None, "breakMin": 0,
            })
            study_counter += 1
            t += study_dur

        break_dur = min(15, nxt - t)
        if break_dur > 0:
            last = sessions[-1] if sessions else None
            if last and last["type"] == "study" and last["start"] == study_start:
                last["breakStart"] = t
                last["end"] += break_dur
                last["breakMin"] += break_dur
            else:
                sessions.append({
                    "id": f"b{t}", "type": "break", "name": "Break",
                    "start": t, "end": t + break_dur, "enabled": True,
                    "breakStart": None, "breakMin": 0,
                })
            t += break_dur

    return sessions


def minutes_to_time(m):
    h = (m // 60) % 24
    mm = m % 60
    return f"{h:02d}:{mm:02d}"


def now_minutes():
    n = datetime.now()
    return n.hour * 60 + n.minute


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def load_overrides():
    try:
        with open(APPDATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"names": {}, "enabled": {}}


def save_overrides(data):
    os.makedirs(os.path.dirname(APPDATA_FILE), exist_ok=True)
    with open(APPDATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Alarm window — full screen, always on top, unclosable until solved
# ---------------------------------------------------------------------------
class AlarmWindow(tk.Toplevel):
    def __init__(self, master, label):
        super().__init__(master)
        self.title("FocusFlow Alarm")
        self.configure(bg="#09090B")
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._block_close)  # disable the X button
        self.bind("<Escape>", lambda e: None)  # block Escape too
        self.grab_set()  # modal — blocks interaction with the main window

        self.correct_answer = None
        self._stop_sound = False

        container = tk.Frame(self, bg="#09090B")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(container, text="⏰", font=("Segoe UI Emoji", 56), bg="#09090B").pack(pady=(0, 12))
        tk.Label(container, text="Time to switch!", font=("Segoe UI", 24, "bold"),
                 fg="#E4E4E7", bg="#09090B").pack()
        tk.Label(container, text=label, font=("Segoe UI", 13),
                 fg="#A1A1AA", bg="#09090B").pack(pady=(2, 28))

        card = tk.Frame(container, bg="#18181B", padx=32, pady=28)
        card.pack()

        self.question_label = tk.Label(card, text="", font=("Consolas", 26, "bold"),
                                        fg="#E4E4E7", bg="#18181B")
        self.question_label.pack(pady=(0, 18))

        self.answer_var = tk.StringVar()
        self.answer_entry = tk.Entry(card, textvariable=self.answer_var, font=("Consolas", 22),
                                      justify="center", width=12, bg="#09090B", fg="#E4E4E7",
                                      insertbackground="#E4E4E7", relief="flat")
        self.answer_entry.pack(ipady=10)
        self.answer_entry.bind("<Return>", lambda e: self._check_answer())

        self.error_label = tk.Label(card, text="", font=("Segoe UI", 10), fg="#EF4444", bg="#18181B")
        self.error_label.pack(pady=(6, 0))

        submit_btn = tk.Button(container, text="SUBMIT & STOP ALARM", font=("Segoe UI", 13, "bold"),
                                bg="#FACC15", fg="#09090B", relief="flat", padx=20, pady=14,
                                command=self._check_answer, cursor="hand2")
        submit_btn.pack(pady=(24, 0), fill="x")

        self._new_question()
        self.after(200, lambda: self.answer_entry.focus_force())
        self._start_sound_loop()

    def _new_question(self):
        q, a = random.choice(MATH_BANK)
        self.correct_answer = a
        self.question_label.config(text=q)
        self.answer_var.set("")

    def _check_answer(self):
        try:
            val = int(self.answer_var.get().strip())
        except ValueError:
            self.error_label.config(text="Enter a number")
            return
        if val == self.correct_answer:
            self._stop_sound = True
            self.grab_release()
            self.destroy()
        else:
            self.error_label.config(text="Wrong, try again")
            self._new_question()

    def _block_close(self):
        pass  # ignore the close request entirely

    def _start_sound_loop(self):
        def loop():
            while not self._stop_sound:
                if HAS_WINSOUND:
                    try:
                        winsound.Beep(1000, 500)
                    except Exception:
                        pass
                else:
                    time.sleep(0.5)
                time.sleep(0.4)
        threading.Thread(target=loop, daemon=True).start()


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------
class FocusFlowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FocusFlow")
        self.root.geometry("560x720")
        self.root.configure(bg="#09090B")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.overrides = load_overrides()
        self.sessions = generate_schedule()
        self._apply_overrides()

        self.fired_today = set()
        self.current_day = datetime.now().date()

        self._build_ui()
        self._refresh_list()

        self.running = True
        threading.Thread(target=self._tick_loop, daemon=True).start()
        self._update_clock()

    # ---------- data ----------
    def _apply_overrides(self):
        names = self.overrides.get("names", {})
        enabled = self.overrides.get("enabled", {})
        for s in self.sessions:
            if s["type"] == "study" and s["id"] in names:
                s["name"] = names[s["id"]]
            if s["id"] in enabled:
                s["enabled"] = enabled[s["id"]]

    def _save(self):
        data = {"names": {}, "enabled": {}}
        for s in self.sessions:
            if s["type"] == "study":
                data["names"][s["id"]] = s["name"]
            data["enabled"][s["id"]] = s["enabled"]
        save_overrides(data)

    # ---------- UI ----------
    def _build_ui(self):
        header = tk.Frame(self.root, bg="#09090B")
        header.pack(fill="x", padx=16, pady=(16, 8))

        left = tk.Frame(header, bg="#09090B")
        left.pack(side="left")
        tk.Label(left, text="FocusFlow", font=("Segoe UI", 22, "bold"),
                 fg="#E4E4E7", bg="#09090B").pack(anchor="w")
        tk.Label(left, text="Daily Study Rhythm", font=("Segoe UI", 10),
                 fg="#A1A1AA", bg="#09090B").pack(anchor="w")

        right = tk.Frame(header, bg="#09090B")
        right.pack(side="right")
        self.clock_label = tk.Label(right, text="", font=("Consolas", 16),
                                     fg="#E4E4E7", bg="#09090B")
        self.clock_label.pack(anchor="e")
        self.countdown_label = tk.Label(right, text="--:--", font=("Consolas", 18, "bold"),
                                         fg="#FACC15", bg="#09090B")
        self.countdown_label.pack(anchor="e")

        tk.Frame(self.root, bg="#27272A", height=1).pack(fill="x", padx=16)

        stats = tk.Frame(self.root, bg="#09090B")
        stats.pack(fill="x", padx=16, pady=10)
        self.study_label = tk.Label(stats, text="Study: 0h 0m", font=("Segoe UI", 10, "bold"),
                                     fg="#34D399", bg="#09090B")
        self.study_label.pack(side="left")
        self.break_label = tk.Label(stats, text="   Break: 0h 0m", font=("Segoe UI", 10, "bold"),
                                     fg="#3B82F6", bg="#09090B")
        self.break_label.pack(side="left")
        reset_btn = tk.Button(stats, text="Reset", font=("Segoe UI", 9), fg="#FACC15",
                               bg="#09090B", relief="flat", command=self._reset,
                               cursor="hand2", activebackground="#09090B")
        reset_btn.pack(side="right")

        canvas_frame = tk.Frame(self.root, bg="#09090B")
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.canvas = tk.Canvas(canvas_frame, bg="#09090B", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg="#09090B")

        self.list_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw", width=520)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        accent = {"study": "#3B82F6", "break": "#34D399", "meal": "#F59E0B"}
        now = now_minutes()

        for s in self.sessions:
            active = s["start"] <= now < s["end"]
            border = "#FACC15" if active else accent[s["type"]]

            card = tk.Frame(self.list_frame, bg="#18181B", highlightbackground=border,
                             highlightthickness=2, padx=14, pady=12)
            card.pack(fill="x", pady=5)
            if not s["enabled"]:
                card.configure(bg="#2B1414")

            var = tk.BooleanVar(value=s["enabled"])
            cb = tk.Checkbutton(card, variable=var, bg=card["bg"], activebackground=card["bg"],
                                 command=lambda s=s, v=var: self._toggle(s, v))
            cb.grid(row=0, column=0, rowspan=2, padx=(0, 10))

            time_lbl = tk.Label(card, text=f'{minutes_to_time(s["start"])} — {minutes_to_time(s["end"])}',
                                 font=("Consolas", 9), fg="#A1A1AA", bg=card["bg"])
            time_lbl.grid(row=0, column=1, sticky="w")

            name_lbl = tk.Label(card, text=s["name"], font=("Segoe UI", 13, "bold"),
                                 fg="#E4E4E7", bg=card["bg"], cursor="hand2" if s["type"] == "study" else "")
            name_lbl.grid(row=1, column=1, sticky="w")
            if s["type"] == "study":
                name_lbl.bind("<Button-1>", lambda e, s=s: self._rename(s))

            type_lbl = tk.Label(card, text=s["type"], font=("Segoe UI", 9, "bold"),
                                 fg=accent[s["type"]], bg=card["bg"])
            type_lbl.grid(row=0, column=2, sticky="e", padx=(20, 0))
            dur_lbl = tk.Label(card, text=f'{s["end"] - s["start"]} min', font=("Segoe UI", 9),
                                fg="#A1A1AA", bg=card["bg"])
            dur_lbl.grid(row=1, column=2, sticky="e", padx=(20, 0))
            card.grid_columnconfigure(1, weight=1)

        self._update_stats()

    def _toggle(self, s, var):
        s["enabled"] = var.get()
        self._save()
        self._refresh_list()

    def _rename(self, s):
        new_name = simpledialog.askstring("Rename session", "New name:", initialvalue=s["name"],
                                           parent=self.root)
        if new_name and new_name.strip():
            s["name"] = new_name.strip()
            self._save()
            self._refresh_list()

    def _reset(self):
        if messagebox.askyesno("Reset", "Reset all changes to defaults?"):
            try:
                os.remove(APPDATA_FILE)
            except OSError:
                pass
            self.overrides = {"names": {}, "enabled": {}}
            self.sessions = generate_schedule()
            self._refresh_list()

    def _update_stats(self):
        study = brk = 0
        for s in self.sessions:
            if not s["enabled"]:
                continue
            if s["type"] == "study":
                study += (s["end"] - s["start"]) - s["breakMin"]
                brk += s["breakMin"]
            elif s["type"] == "break":
                brk += s["end"] - s["start"]
        self.study_label.config(text=f"Study: {study // 60}h {study % 60}m")
        self.break_label.config(text=f"   Break: {brk // 60}h {brk % 60}m")

    def _update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        now = now_minutes()
        active = next((s for s in self.sessions if s["start"] <= now < s["end"]), None)
        if active:
            left = active["end"] - now
            self.countdown_label.config(text=f"{left:02d} min left")
        else:
            self.countdown_label.config(text="--:--")
        self.root.after(1000, self._update_clock)

    # ---------- alarm scheduling loop ----------
    def _tick_loop(self):
        while self.running:
            today = datetime.now().date()
            if today != self.current_day:
                self.fired_today.clear()
                self.current_day = today
                self.sessions = generate_schedule()
                self._apply_overrides()
                self.root.after(0, self._refresh_list)

            now = now_minutes()
            for s in self.sessions:
                if not s["enabled"] or s["type"] == "meal":
                    continue
                start_key = (s["id"], "start")
                if now == s["start"] and start_key not in self.fired_today:
                    self.fired_today.add(start_key)
                    self.root.after(0, lambda s=s: self._fire_alarm(f'{s["name"]} is starting'))
                if s.get("breakStart") is not None:
                    brk_key = (s["id"], "break")
                    if now == s["breakStart"] and brk_key not in self.fired_today:
                        self.fired_today.add(brk_key)
                        self.root.after(0, lambda: self._fire_alarm("Break time!"))
            time.sleep(1)

    def _fire_alarm(self, label):
        AlarmWindow(self.root, label)

    def _on_close(self):
        if messagebox.askyesno("Quit", "Quit FocusFlow? Alarms will stop working while it's closed."):
            self.running = False
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = FocusFlowApp(root)
    root.mainloop()
