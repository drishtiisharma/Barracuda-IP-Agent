"""Barracuda IP Removal Agent - run with:  python main.py   (or double-click the built .exe)"""
import os
import sys
import traceback
from pathlib import Path

# Make imports work no matter which folder you launch from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import BASE_DIR  # noqa: E402


def _prepare_packaged_mode():
    """A windowed .exe has no console: give stdout/stderr a real file so nothing crashes on print()."""
    if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
        log = open(Path(BASE_DIR) / "agent_log.txt", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def main():
    _prepare_packaged_mode()
    if "--selftest" in sys.argv:
        import selftest
        sys.exit(selftest.run())
    try:
        from ui.app import App
        App().run()
    except Exception:                                   # noqa: BLE001
        text = traceback.format_exc()
        try:
            (Path(BASE_DIR) / "crash_log.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Barracuda IP Removal Agent crashed", text[-1500:])
        except Exception:                               # noqa: BLE001
            print(text)


if __name__ == "__main__":
    main()
