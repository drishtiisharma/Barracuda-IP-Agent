import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from config.settings import OUTPUT_DIRECTORY
from services.classification import LISTED, NOT_LISTED, DUPLICATE, INVALID, ERROR, BLOCKED
from storage.exporter import export_rows
from ui.icon import apply_icon

COLUMNS = ("ip_address", "status", "confirmation_number", "message", "started_at", "completed_at")
HEADINGS = ("IP", "Status", "Confirmation number", "Message", "Started", "Completed")
WIDTHS = (120, 120, 210, 420, 140, 140)


class ResultsDialog(tk.Toplevel):
    """
    Shows the result of a run (job_id given) and lets you flip to the full log table
    inside the same window with 'View Logs'. job_id=None opens straight on the logs.
    """

    def __init__(self, parent, db, job_id=None, state="Finished", csv_path=None):
        super().__init__(parent)
        self.db, self.job_id, self.csv_path = db, job_id, csv_path
        self.showing_logs = job_id is None
        self.title("Results" if job_id else "Logs")
        apply_icon(self)
        self.geometry("1100x520+60+80")

        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, padding=(12, 10), font=("TkDefaultFont", 11, "bold")).pack(fill="x")
        self.state = state

        search = ttk.Frame(self, padding=(12, 0))
        search.pack(fill="x")
        self.query = tk.StringVar()
        self.search_row = search
        ttk.Label(search, text="Search").pack(side="left")
        entry = ttk.Entry(search, textvariable=self.query, width=30)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(search, text="Go", command=self.refresh).pack(side="left")

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=COLUMNS, show="headings")
        for col, head, width in zip(COLUMNS, HEADINGS, WIDTHS):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, minwidth=80)
        ys = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.tree.tag_configure(LISTED, foreground="#1b7f2a")
        self.tree.tag_configure(NOT_LISTED, foreground="#555555")
        self.tree.tag_configure(DUPLICATE, foreground="#a66a00")
        for bad in (ERROR, BLOCKED, INVALID):
            self.tree.tag_configure(bad, foreground="#b00020")

        buttons = ttk.Frame(self, padding=12)
        buttons.pack(fill="x")
        self.toggle_btn = ttk.Button(buttons, command=self.toggle)
        self.export_btn = ttk.Button(buttons, text="Export Results", command=self.export)
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
        if job_id:
            self.export_btn.pack(side="right", padx=6)
            self.toggle_btn.pack(side="left")
        self.refresh()

    def toggle(self):
        self.showing_logs = not self.showing_logs
        self.refresh()

    def refresh(self):
        if self.showing_logs:
            rows = self.db.all_logs(self.query.get())
            self.toggle_btn.configure(text="Back to Results")
            self.title("Logs (all runs, newest first)")
            self.summary_var.set(f"All logs - {len(rows)} entries shown")
        else:
            rows = self.db.get_job(self.job_id)
            self.toggle_btn.configure(text="View Logs")
            self.title("Results")
            count = lambda s: sum(r["status"] == s for r in rows)
            self.summary_var.set(
                f"Run {self.state.lower()}  -  Listed (submitted): {count(LISTED)}   Not listed: {count(NOT_LISTED)}   "
                f"Duplicate: {count(DUPLICATE)}   Invalid: {count(INVALID)}   Errors: {count(ERROR) + count(BLOCKED)}")
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", values=[r.get(c, "") or "" for c in COLUMNS], tags=(r["status"],))

    def export(self):
        rows = self.db.get_job(self.job_id)
        if not rows:
            messagebox.showinfo("Export Results", "Nothing to export.", parent=self)
            return
        Path(OUTPUT_DIRECTORY).mkdir(parents=True, exist_ok=True)
        dest = filedialog.asksaveasfilename(
            parent=self, title="Export results", initialdir=OUTPUT_DIRECTORY,
            initialfile=Path(self.csv_path).name if self.csv_path else "results.csv",
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not dest:
            return
        try:
            saved = export_rows(rows, dest)
            messagebox.showinfo("Export Results", f"Saved to:\n{saved}", parent=self)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
