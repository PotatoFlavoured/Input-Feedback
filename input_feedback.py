"""Input Feedback - a Fortnite edit-input overlay.

Shows a small circle on top of the game:
  green = your edits are going through
  red   = you made an input mistake (e.g. an edit that never got confirmed)
  grey  = paused / Fortnite not focused

The program only *reads* your keyboard and mouse. It never sends inputs and
never touches the game's memory.
"""
from __future__ import annotations

import ctypes
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk

from pynput import keyboard, mouse

import config
from keys import button_to_name, display_name, key_to_name
from tracker import ERROR, SUCCESS, WARNING, EditTracker

IS_WINDOWS = sys.platform == "win32"

GREEN = "#22c55e"
RED = "#ef4444"
GREY = "#6b7280"
TRANSPARENT = "#010203"  # painted pixels of this colour are see-through

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def fortnite_focused() -> bool:
    if not IS_WINDOWS:
        return True
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return "fortnite" in buf.value.lower()


class Overlay:
    """Borderless, always-on-top, click-through window with one circle."""

    def __init__(self, root: tk.Tk, cfg: dict, on_moved):
        self.cfg = cfg
        self.on_moved = on_moved
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass  # not supported outside Windows
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.circle = None
        self.color = None
        self.locked = True
        self._drag = (0, 0)
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.apply_geometry()
        self.set_locked(True)

    def apply_geometry(self) -> None:
        o = self.cfg["overlay"]
        size = int(o["size"])
        self.win.geometry(f"{size}x{size}+{int(o['x'])}+{int(o['y'])}")
        self.canvas.delete("all")
        pad = 2
        self.circle = self.canvas.create_oval(
            pad, pad, size - pad, size - pad,
            fill=self.color or GREEN, outline="#111111", width=2)

    def set_color(self, color: str) -> None:
        if color != self.color:
            self.color = color
            self.canvas.itemconfigure(self.circle, fill=color)

    def set_locked(self, locked: bool) -> None:
        """Locked = clicks pass straight through to the game."""
        self.locked = locked
        if not IS_WINDOWS:
            return
        self.win.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.win.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if locked:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def keep_on_top(self) -> None:
        self.win.attributes("-topmost", True)
        self.win.lift()

    def _drag_start(self, e):
        if not self.locked:
            self._drag = (e.x, e.y)

    def _drag_move(self, e):
        if self.locked:
            return
        x = self.win.winfo_x() + e.x - self._drag[0]
        y = self.win.winfo_y() + e.y - self._drag[1]
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, _e):
        if not self.locked:
            self.on_moved(self.win.winfo_x(), self.win.winfo_y())


class App:
    def __init__(self):
        self.cfg = config.load()
        self.tracker = EditTracker(config.tracker_settings(self.cfg))
        self.events: queue.Queue = queue.Queue()

        self.paused = False
        self.focused = True
        self.last_focus_check = 0.0
        self.last_topmost = 0.0
        self.red_until = 0.0
        self.capturing = None       # bind key currently waiting for an input
        self.capture_since = 0.0
        self.stats = {"confirmed": 0, "errors": 0, "slow": 0}

        self.root = tk.Tk()
        self.root.title("Input Feedback")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.bind_labels = {}
        self.bind_buttons = {}
        self._build_ui()

        self.overlay = Overlay(self.root, self.cfg, self._overlay_moved)

        self.kb_listener = keyboard.Listener(on_press=self._kb_press, on_release=self._kb_release)
        self.mouse_listener = mouse.Listener(on_click=self._mouse_click, on_scroll=self._mouse_scroll)
        self.kb_listener.start()
        self.mouse_listener.start()

        self.root.after(10, self._pump)

    # -- input hooks (run on listener threads; only push to the queue) ----

    def _kb_press(self, key):
        self.events.put(("press", key_to_name(key), time.monotonic()))

    def _kb_release(self, key):
        self.events.put(("release", key_to_name(key), time.monotonic()))

    def _mouse_click(self, _x, _y, button, pressed):
        kind = "press" if pressed else "release"
        self.events.put((kind, button_to_name(button), time.monotonic()))

    def _mouse_scroll(self, _x, _y, _dx, dy):
        if dy == 0:
            return
        name = "wheel_up" if dy > 0 else "wheel_down"
        t = time.monotonic()
        self.events.put(("press", name, t))
        self.events.put(("release", name, t))

    # -- main loop --------------------------------------------------------

    def _pump(self):
        now = time.monotonic()

        if self.cfg["only_when_fortnite_focused"] and now - self.last_focus_check > 0.25:
            self.last_focus_check = now
            focused = fortnite_focused()
            if focused != self.focused:
                self.focused = focused
                self.tracker.reset()
        elif not self.cfg["only_when_fortnite_focused"]:
            self.focused = True

        while True:
            try:
                kind, name, t = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle(kind, name, t)

        if self._tracking():
            self._feedback(self.tracker.tick(now))

        if now - self.last_topmost > 2:
            self.last_topmost = now
            self.overlay.keep_on_top()

        if not self._tracking():
            color = GREY
        elif now < self.red_until:
            color = RED
        else:
            color = GREEN
        self.overlay.set_color(color)
        self._update_status()

        self.root.after(10, self._pump)

    def _tracking(self) -> bool:
        return not self.paused and self.focused and self.capturing is None

    def _handle(self, kind, name, t):
        if self.capturing is not None:
            if kind == "press" and t > self.capture_since:
                self._finish_capture(None if name == "esc" else name)
            # keep held-key bookkeeping right while capturing
            if kind == "release":
                self.tracker.down.discard(name)
            return

        if kind == "press" and name == self.cfg["pause_key"]:
            self.paused = not self.paused
            self.tracker.reset()
            return

        if not self._tracking():
            if kind == "release":
                self.tracker.down.discard(name)
            return

        if kind == "press":
            self._feedback(self.tracker.on_press(name, t))
        else:
            self._feedback(self.tracker.on_release(name, t))

    def _feedback(self, fb):
        if fb is None:
            return
        now = time.monotonic()
        if fb.kind == SUCCESS:
            self.stats["confirmed"] += 1
            self.red_until = 0.0
        else:
            self.stats["errors" if fb.kind == ERROR else "slow"] += 1
            self.red_until = now + int(self.cfg["red_ms"]) / 1000
            stamp = time.strftime("%H:%M:%S")
            tag = "MISSED" if fb.kind == ERROR else "SLOW"
            self.log.insert(0, f"{stamp}  {tag}  {fb.message}")
            self.log.delete(50, "end")
        self.last_msg.set(fb.message)
        self._update_stats()

    # -- settings window --------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self.root, padding=10)
        frame.grid(sticky="nsew")

        # Mode
        mode = ttk.LabelFrame(frame, text="Edit mode", padding=8)
        mode.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        self.eor_var = tk.BooleanVar(value=self.cfg["edit_on_release"])
        ttk.Radiobutton(mode, text="Edit on release ON", variable=self.eor_var, value=True,
                        command=self._settings_changed).grid(row=0, column=0, sticky="w")
        ttk.Label(mode, foreground="#555",
                  text="Press edit → hold left click on tiles → RELEASE left click to confirm"
                  ).grid(row=1, column=0, sticky="w", padx=20)
        ttk.Radiobutton(mode, text="Edit on release OFF", variable=self.eor_var, value=False,
                        command=self._settings_changed).grid(row=2, column=0, sticky="w")
        ttk.Label(mode, foreground="#555",
                  text="Press edit → left click tiles → press EDIT again to confirm"
                  ).grid(row=3, column=0, sticky="w", padx=20)

        # Binds
        edit_box = ttk.LabelFrame(frame, text="Edit binds", padding=8)
        edit_box.grid(row=1, column=0, sticky="nsew", **pad)
        for i, (key, label) in enumerate(config.EDIT_BINDS):
            self._bind_row(edit_box, i, key, label)

        exit_box = ttk.LabelFrame(frame, text="Build & weapon binds (these leave edit)", padding=8)
        exit_box.grid(row=1, column=1, rowspan=2, sticky="nsew", **pad)
        for i, (key, label) in enumerate(config.EXIT_BINDS):
            self._bind_row(exit_box, i, key, label)

        # Timing / overlay options
        opts = ttk.LabelFrame(frame, text="Options", padding=8)
        opts.grid(row=2, column=0, sticky="nsew", **pad)
        self.num_vars = {}
        rows = [
            ("max_hold_ms", "Warn if select held longer than (ms, 0 = off)", 0, 5000, 50),
            ("red_ms", "Keep circle red for (ms)", 200, 10000, 100),
            ("edit_timeout_ms", "Forget an idle edit after (ms, 0 = off)", 0, 10000, 250),
        ]
        r = 0
        for key, label, lo, hi, step in rows:
            r = self._spin_row(opts, r, label, lo, hi, step, key)
        for key, label, lo, hi, step in [("size", "Circle size (px)", 10, 200, 2),
                                         ("x", "Overlay X position", -4000, 8000, 10),
                                         ("y", "Overlay Y position", -4000, 8000, 10)]:
            r = self._spin_row(opts, r, label, lo, hi, step, key, overlay=True)

        self.focus_var = tk.BooleanVar(value=self.cfg["only_when_fortnite_focused"])
        ttk.Checkbutton(opts, text="Only track while Fortnite is the active window",
                        variable=self.focus_var, command=self._settings_changed
                        ).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        self.unlock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Unlock overlay (drag the circle to move it)",
                        variable=self.unlock_var, command=self._toggle_unlock
                        ).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        pause_row = ttk.Frame(opts)
        pause_row.grid(row=r, column=0, columnspan=2, sticky="w")
        ttk.Label(pause_row, text="Pause / resume hotkey:").pack(side="left")
        self.bind_labels["pause_key"] = ttk.Label(pause_row, width=12,
                                                  text=display_name(self.cfg["pause_key"]))
        self.bind_labels["pause_key"].pack(side="left", padx=6)
        btn = ttk.Button(pause_row, text="Set", width=5,
                         command=lambda: self._start_capture("pause_key"))
        btn.pack(side="left")
        self.bind_buttons["pause_key"] = btn

        # Stats
        stats = ttk.LabelFrame(frame, text="Session", padding=8)
        stats.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.stats_var = tk.StringVar()
        ttk.Label(stats, textvariable=self.stats_var, font=("Segoe UI", 10, "bold")
                  ).grid(row=0, column=0, sticky="w")
        ttk.Button(stats, text="Reset stats", command=self._reset_stats).grid(row=0, column=1, sticky="e")
        stats.columnconfigure(0, weight=1)
        self.last_msg = tk.StringVar(value="Waiting for your first edit...")
        ttk.Label(stats, textvariable=self.last_msg, wraplength=640).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 4))
        self.log = tk.Listbox(stats, height=6, width=100)
        self.log.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, foreground="#555").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=8)
        self._update_stats()

    def _bind_row(self, parent, row, key, label):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=1)
        lbl = ttk.Label(parent, width=14, text=display_name(self.cfg["binds"].get(key)),
                        font=("Segoe UI", 9, "bold"))
        lbl.grid(row=row, column=1, sticky="w", padx=6)
        btn = ttk.Button(parent, text="Set", width=5, command=lambda: self._start_capture(key))
        btn.grid(row=row, column=2)
        ttk.Button(parent, text="Clear", width=6,
                   command=lambda: self._set_bind(key, None)).grid(row=row, column=3, padx=(4, 0))
        self.bind_labels[key] = lbl
        self.bind_buttons[key] = btn

    def _spin_row(self, parent, row, label, lo, hi, step, key, overlay=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=1)
        value = self.cfg["overlay"][key] if overlay else self.cfg[key]
        var = tk.StringVar(value=str(value))
        spin = ttk.Spinbox(parent, from_=lo, to=hi, increment=step, width=8, textvariable=var,
                           command=self._settings_changed)
        spin.grid(row=row, column=1, sticky="w", padx=6)
        spin.bind("<FocusOut>", lambda _e: self._settings_changed())
        spin.bind("<Return>", lambda _e: self._settings_changed())
        self.num_vars[(key, overlay)] = var
        return row + 1

    def _start_capture(self, key):
        if self.capturing is not None:
            self._finish_capture(None)
        self.capturing = key
        self.capture_since = time.monotonic()
        self.bind_labels[key].configure(text="Press a key / button... (Esc = cancel)")
        self.tracker.reset()

    def _finish_capture(self, name):
        key = self.capturing
        self.capturing = None
        if key is None:
            return
        if name is None:
            self.bind_labels[key].configure(text=display_name(self._get_bind(key)))
            return
        self._set_bind(key, name)

    def _get_bind(self, key):
        return self.cfg["pause_key"] if key == "pause_key" else self.cfg["binds"].get(key)

    def _set_bind(self, key, name):
        if key == "pause_key":
            self.cfg["pause_key"] = name
        else:
            self.cfg["binds"][key] = name
        self.bind_labels[key].configure(text=display_name(name))
        self._settings_changed()

    def _settings_changed(self):
        self.cfg["edit_on_release"] = bool(self.eor_var.get())
        self.cfg["only_when_fortnite_focused"] = bool(self.focus_var.get())
        for (key, overlay), var in self.num_vars.items():
            try:
                value = int(float(var.get()))
            except ValueError:
                continue
            if overlay:
                self.cfg["overlay"][key] = value
            else:
                self.cfg[key] = value
        self.tracker.configure(config.tracker_settings(self.cfg))
        if hasattr(self, "overlay"):
            self.overlay.apply_geometry()
        self._warn_duplicates()
        config.save(self.cfg)

    def _warn_duplicates(self):
        seen = {}
        for key, label in config.EDIT_BINDS + config.EXIT_BINDS:
            name = self.cfg["binds"].get(key)
            if name:
                seen.setdefault(name, []).append(label)
        dupes = [f"{display_name(n)}: {', '.join(ls)}" for n, ls in seen.items() if len(ls) > 1]
        self.dupe_warning = ("  |  Same key on: " + "; ".join(dupes)) if dupes else ""

    def _toggle_unlock(self):
        self.overlay.set_locked(not self.unlock_var.get())

    def _overlay_moved(self, x, y):
        self.cfg["overlay"]["x"] = x
        self.cfg["overlay"]["y"] = y
        self.num_vars[("x", True)].set(str(x))
        self.num_vars[("y", True)].set(str(y))
        config.save(self.cfg)

    def _reset_stats(self):
        self.stats = {"confirmed": 0, "errors": 0, "slow": 0}
        self.log.delete(0, "end")
        self.last_msg.set("Stats reset.")
        self._update_stats()

    def _update_stats(self):
        s = self.stats
        total = s["confirmed"] + s["errors"]
        acc = f"{100 * s['confirmed'] / total:.0f}%" if total else "-"
        self.stats_var.set(f"Confirmed edits: {s['confirmed']}    Missed edits: {s['errors']}    "
                           f"Slow releases: {s['slow']}    Accuracy: {acc}")

    def _update_status(self):
        pause = display_name(self.cfg["pause_key"])
        if self.capturing is not None:
            text = "Setting a bind..."
        elif self.paused:
            text = f"PAUSED - press {pause} to resume"
        elif not self.focused:
            text = "Waiting for Fortnite to be the active window"
        else:
            text = f"Tracking - press {pause} to pause"
        text += getattr(self, "dupe_warning", "")
        if self.status_var.get() != text:
            self.status_var.set(text)

    def quit(self):
        config.save(self.cfg)
        self.kb_listener.stop()
        self.mouse_listener.stop()
        self.root.destroy()

    def run(self):
        self._warn_duplicates()
        self.root.mainloop()


def main():
    if IS_WINDOWS:
        try:  # keep the overlay sharp and positioned correctly on scaled displays
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().run()


if __name__ == "__main__":
    main()
