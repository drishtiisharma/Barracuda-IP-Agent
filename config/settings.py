"""
All the knobs you may want to change live here.
"""
import os
import sys
from pathlib import Path


def _data_root():
    """Where profile, logs and CSVs live. Next to the .exe when packaged, next to the code otherwise."""
    if getattr(sys, "frozen", False):                      # running as the packaged .exe
        folder = Path(sys.executable).resolve().parent / "BarracudaData"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write_test"
            probe.write_text("x")
            probe.unlink()
            return folder
        except OSError:                                    # exe sits in a read-only place
            fallback = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BarracudaIPAgent"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
    return Path(__file__).resolve().parent.parent


BASE_DIR = _data_root()

# ----------------------------------------------------------------------------
# Barracuda
# ----------------------------------------------------------------------------
REMOVAL_URL = os.environ.get("BARRACUDA_REMOVAL_URL", "https://www.barracudacentral.org/rbl/removal-request")

# ----------------------------------------------------------------------------
# Anti-bot / human-like behaviour
# ----------------------------------------------------------------------------
# Random wait between two IPs. Every wait is a fresh random number in this range
# (e.g. 1 -> 10 means sometimes 1.3s, sometimes 8.7s, sometimes 4.2s ...).
DELAY_MIN_SECONDS = 1.0
DELAY_MAX_SECONDS = 10.0

# After this many IPs the browser window is closed and a brand-new window
# (fresh session / cookies) is opened.
SESSION_REFRESH_THRESHOLD = 10

# Typing speed (milliseconds per key; a random value in the range is used).
TYPING_DELAY_MS = (45, 130)          # short fields: IP, email, name, phone
REASON_TYPING_DELAY_MS = (6, 18)     # long "reason" text

# Small random pauses so the form is not filled at machine speed.
FIELD_PAUSE_SECONDS = (0.3, 0.9)         # between two fields
PRE_SUBMIT_PAUSE_SECONDS = (0.8, 2.0)    # before pressing "Submit Request"

# How long to wait for Barracuda to ANSWER after pressing "Submit Request".
# None = wait as long as it takes (you can still press Stop). Or set a number of seconds.
RESPONSE_TIMEOUT_SECONDS = None
# Time allowed for opening the removal-request page itself (seconds).
PAGE_LOAD_TIMEOUT_SECONDS = 180

# Stop the whole batch after this many errors in a row (site down / blocked).
MAX_CONSECUTIVE_ERRORS = 3

# ----------------------------------------------------------------------------
# Browser window behaviour
# ----------------------------------------------------------------------------
# The browser is visible (you can watch the form being filled) but the script never
# calls bring_to_front(), and Chromium is told not to throttle itself when other
# windows cover it - so you can keep working in other apps.
# Window placement as a fraction of the screen: x, y, width, height
BROWSER_WINDOW_FRACTION = (0.42, 0.0, 0.58, 0.92)

# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
DATABASE_PATH = str(BASE_DIR / "data" / "agent_logs.db")
PROFILE_PATH = str(BASE_DIR / "config" / "profile.json")
OUTPUT_DIRECTORY = str(BASE_DIR / "output")

# ----------------------------------------------------------------------------
# Input limits
# ----------------------------------------------------------------------------
RANGE_CONFIRMATION_THRESHOLD = 50
MAX_RANGE_SIZE = 4096
