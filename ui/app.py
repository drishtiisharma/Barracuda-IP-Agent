import queue
import os
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from browser.barracuda import BarracudaClient
from config.settings import DATABASE_PATH, OUTPUT_DIRECTORY, BROWSER_WINDOW_FRACTION
from services.runner import BatchRunner
from storage.database import LogDatabase
from ui.icon import apply_icon
from ui.main_dialog import MainDialog
from ui.profile_dialog import ProfileDialog
from ui.results_dialog import ResultsDialog


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()                       # only dialogs are shown, never an empty main window
        apply_icon(self.root)                      # logo for this and every dialog opened later
        self.db = LogDatabase(DATABASE_PATH)
        self.events = queue.Queue()
        self.runner = None
        self.job_id = self.csv_path = None
        self.total = self.done = 0

        self.profile = ProfileDialog(self.root).show()      # dialog 1: profile
        if not self.profile:
            self.root.destroy()
            self.root = None
            return
        self.main = MainDialog(self.root, self)             # dialog 2: Single / Range / Random
        self.root.after(150, self._poll)

    def run(self):
        if self.root:
            self.root.mainloop()

    # ---------------------------------------------------------------- profile / logs
    def edit_profile(self):
        if self.runner and self.runner.is_alive():
            messagebox.showinfo("Busy", "Wait for the current run to finish first.", parent=self.main)
            return
        new = ProfileDialog(self.root).show()
        if new:
            self.profile = new
            self.main.set_status("Profile saved.")

    def show_all_logs(self):
        ResultsDialog(self.root, self.db, job_id=None)

    # ---------------------------------------------------------------- run control
    def _window_rect(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        fx, fy, fw, fh = BROWSER_WINDOW_FRACTION
        return int(sw * fx), int(sh * fy), int(sw * fw), int(sh * fh)

    def start_batch(self, valid, invalid, duplicates):
        if self.runner and self.runner.is_alive():
            return
        self.job_id = f"{int(time.time())}-{os.urandom(4).hex()}"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = str(Path(OUTPUT_DIRECTORY) / f"results_{stamp}.csv")
        self.total = len(valid) + len(invalid) + len(duplicates)
        self.done = 0
        profile, rect = dict(self.profile), self._window_rect()
        factory = lambda cb, stop: BarracudaClient(profile, window_rect=rect, status_cb=cb, should_stop=stop)
        self.runner = BatchRunner(self.job_id, valid, invalid, duplicates, self.db, self.csv_path, self.events, factory)
        self.main.set_running(True, self.total)
        self.main.set_status("Starting...")
        self.runner.start()

    def pause_resume(self):
        if self.runner:
            paused = self.runner.toggle_pause()
            self.main.set_pause_label(paused)
            self.main.set_status("Paused (the current IP finishes first)." if paused else "Resumed.")

    def stop(self):
        if self.runner:
            self.runner.stop()
            self.main.set_status("Stopping after the current IP...")

    def quit(self):
        if self.runner and self.runner.is_alive():
            if not messagebox.askyesno("Run in progress", "Stop the current run and close?", parent=self.main):
                return
            self.runner.stop()
        self.root.destroy()

    # ---------------------------------------------------------------- event loop
    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.main.set_status(payload)
                elif kind == "row":
                    self.done += 1
                    self.main.set_progress(self.done)
                elif kind == "fatal":
                    messagebox.showerror("Problem", payload, parent=self.main)
                elif kind == "done":
                    self._finished(payload)
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def _finished(self, state):
        self.main.set_running(False, self.total)
        self.main.set_progress(self.done)
        self.main.set_status(f"{state}. Results saved to {self.csv_path}")
        ResultsDialog(self.root, self.db, job_id=self.job_id, state=state, csv_path=self.csv_path)
