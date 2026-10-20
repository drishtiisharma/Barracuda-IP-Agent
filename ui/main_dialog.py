import tkinter as tk
from tkinter import ttk, messagebox

from config.settings import MAX_RANGE_SIZE, RANGE_CONFIRMATION_THRESHOLD
from ui.icon import apply_icon
from services.ip_tools import parse_ip, parse_ip_list, parse_range


class MainDialog(tk.Toplevel):
    """Dialog with three tabs: Single / Range / Random, plus run controls."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Barracuda IP Removal Agent")
        apply_icon(self)
        self.geometry("520x560+40+40")
        self.minsize(480, 520)

        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="Barracuda IP Removal", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Edit Profile", command=app.edit_profile).pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=4)

        # --- Single
        single = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(single, text="Single")
        ttk.Label(single, text="IP address").pack(anchor="w")
        self.single_var = tk.StringVar()
        ttk.Entry(single, textvariable=self.single_var, width=40).pack(anchor="w", pady=8)

        # --- Range
        rng = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(rng, text="Range")
        self.from_var, self.to_var = tk.StringVar(), tk.StringVar()
        ttk.Label(rng, text="From IP").pack(anchor="w")
        ttk.Entry(rng, textvariable=self.from_var, width=40).pack(anchor="w", pady=(4, 12))
        ttk.Label(rng, text="To IP").pack(anchor="w")
        ttk.Entry(rng, textvariable=self.to_var, width=40).pack(anchor="w", pady=4)
        ttk.Label(rng, text=f"Both ends are included. Maximum {MAX_RANGE_SIZE} IPs.").pack(anchor="w", pady=10)

        # --- Random
        rnd = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(rnd, text="Random")
        ttk.Label(rnd, text="Paste IPs (separated by new lines, spaces or commas)").pack(anchor="w")
        self.random_text = tk.Text(rnd, height=12, wrap="word")
        self.random_text.pack(fill="both", expand=True, pady=8)

        # --- Controls
        controls = ttk.Frame(self, padding=(12, 6))
        controls.pack(fill="x")
        self.start_btn = ttk.Button(controls, text="Start", command=self.start)
        self.start_btn.pack(side="left")
        self.pause_btn = ttk.Button(controls, text="Pause", command=self.app.pause_resume, state="disabled")
        self.pause_btn.pack(side="left", padx=6)
        self.stop_btn = ttk.Button(controls, text="Stop", command=self.app.stop, state="disabled")
        self.stop_btn.pack(side="left")
        ttk.Button(controls, text="View Logs", command=self.app.show_all_logs).pack(side="right")

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(4, 0))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, padding=(12, 8), wraplength=480).pack(fill="x")

        self.protocol("WM_DELETE_WINDOW", app.quit)

    # ---- called by the app
    def set_status(self, text):
        self.status_var.set(text)

    def set_running(self, running, total=0):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running else "disabled", text="Pause")
        self.stop_btn.configure(state="normal" if running else "disabled")
        self.progress.configure(maximum=max(1, total), value=0)

    def set_progress(self, done):
        self.progress.configure(value=done)

    def set_pause_label(self, paused):
        self.pause_btn.configure(text="Resume" if paused else "Pause")

    # ---- input collection
    def start(self):
        try:
            valid, invalid, duplicates = self._collect()
        except ValueError as exc:
            messagebox.showerror("Check your input", str(exc), parent=self)
            return
        if not (valid or invalid or duplicates):
            return
        self.app.start_batch(valid, invalid, duplicates)

    def _collect(self):
        tab = self.tabs.index(self.tabs.select())
        if tab == 0:                                           # single
            raw = self.single_var.get().strip()
            if not raw:
                raise ValueError("Enter an IP address.")
            try:
                return [str(parse_ip(raw))], [], []
            except ValueError:
                raise ValueError(f"'{raw}' is not a valid IP address.")
        if tab == 1:                                           # range
            if not self.from_var.get().strip() or not self.to_var.get().strip():
                raise ValueError("Enter both the From and To IP.")
            try:
                ips = parse_range(self.from_var.get(), self.to_var.get(), MAX_RANGE_SIZE)
            except ValueError as exc:
                raise ValueError(str(exc))
            if len(ips) >= RANGE_CONFIRMATION_THRESHOLD and not messagebox.askyesno(
                    "Confirm range", f"This range contains {len(ips)} IPs. Continue?", parent=self):
                return [], [], []
            return ips, [], []
        raw = self.random_text.get("1.0", "end").strip()       # random
        if not raw:
            raise ValueError("Paste at least one IP address.")
        return parse_ip_list(raw)
