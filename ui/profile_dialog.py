import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from config.settings import PROFILE_PATH
from ui.icon import apply_icon

DEFAULT_PROFILE = {
    "email_address": "",
    "customer_name": "",
    "customer_email": "",
    "phone_number": "",
    "reason_for_removal": (
        "Please review this IP address for removal from the Barracuda Reputation Block List. "
        "We can provide additional information about this request if needed."
    ),
}

FIELDS = [
    ("Email Address", "email_address"),
    ("Barracuda Customer Name", "customer_name"),
    ("Barracuda Customer Email Address", "customer_email"),
    ("Phone Number", "phone_number"),
]


def load_profile():
    try:
        saved = json.loads(Path(PROFILE_PATH).read_text(encoding="utf-8"))
        return {**DEFAULT_PROFILE, **{k: v for k, v in saved.items() if k in DEFAULT_PROFILE}}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT_PROFILE)


class ProfileDialog:
    """Modal dialog. show() returns the saved profile dict, or None if the user closed it."""

    def __init__(self, parent):
        self.parent = parent
        self.profile = load_profile()
        self.saved = False

    def show(self):
        win = tk.Toplevel(self.parent)
        win.title("Profile")
        apply_icon(win)
        win.resizable(False, False)

        frame = ttk.Frame(win, padding=18)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Details used in the Barracuda removal form",
                  font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        vars_ = {}
        for i, (label, key) in enumerate(FIELDS, start=1):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=5)
            vars_[key] = tk.StringVar(value=self.profile[key])
            ttk.Entry(frame, textvariable=vars_[key], width=48).grid(row=i, column=1, sticky="ew", pady=5)

        ttk.Label(frame, text="Reason for Removal").grid(row=5, column=0, sticky="nw", padx=(0, 12), pady=5)
        reason = tk.Text(frame, width=48, height=6, wrap="word")
        reason.grid(row=5, column=1, sticky="ew", pady=5)
        reason.insert("1.0", self.profile["reason_for_removal"])

        def save():
            data = {k: v.get().strip() for k, v in vars_.items()}
            data["reason_for_removal"] = reason.get("1.0", "end-1c").strip()
            if any(not v for v in data.values()):
                messagebox.showerror("Missing details", "Please fill in every field.", parent=win)
                return
            try:
                path = Path(PROFILE_PATH)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Could not save", str(exc), parent=win)
                return
            self.profile, self.saved = data, True
            win.destroy()

        ttk.Button(frame, text="Save Profile", command=save).grid(row=6, column=1, sticky="e", pady=(12, 0))
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
        y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.focus_force()
        win.wait_visibility()
        win.grab_set()
        win.wait_window()
        return self.profile if self.saved else None
