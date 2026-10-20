"""Puts the Barracuda logo on every window (title bar + taskbar)."""
import sys
import tkinter as tk
from pathlib import Path


def asset_path(name):
    """assets/<name> - works from source and inside the packaged .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def apply_icon(window):
    """Give `window` (Tk root or Toplevel) the logo. Never raises: a missing icon must not stop the app."""
    try:
        if sys.platform.startswith("win"):
            ico = str(asset_path("logo.ico"))
            window.iconbitmap(ico)                       # this window
            if isinstance(window, tk.Tk):
                window.iconbitmap(default=ico)           # every dialog opened later
        else:
            image = tk.PhotoImage(file=str(asset_path("logo_64.png")))
            window.iconphoto(True, image)
            window._logo_image = image                   # keep a reference so it is not garbage-collected
    except Exception:                                    # noqa: BLE001
        pass
