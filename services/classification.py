"""
Reads the text of the page Barracuda shows AFTER "Submit Request" is pressed.

Two outcomes seen on the real site:

  * red box: 'Your IP address is currently NOT listed as "poor" ...'   -> Not Listed
  * "Request Received ... Your confirmation number is BBR...-...-..."   -> Listed
"""
import re
from dataclasses import dataclass

LISTED = "Listed"
NOT_LISTED = "Not Listed"
DUPLICATE = "Duplicate Request"
INVALID = "Invalid IP"
ERROR = "Error"
BLOCKED = "Blocked"          # captcha / access denied / rate limit -> batch stops

NOT_LISTED_MESSAGE = 'Your IP address is currently NOT listed as "poor" on the Barracuda Reputation System.'

_ERROR_HEADING = "please correct the following errors"
# Words that indicate Barracuda is complaining about a repeated request.
_DUPLICATE_WORDS = ("already", "duplicate", "previously", "recently submitted", "pending request")
_BLOCK_WORDS = ("captcha", "access denied", "temporarily blocked", "too many requests", "rate limit")


@dataclass
class Result:
    status: str
    confirmation_number: str = ""
    message: str = ""


def _clean(text):
    return " ".join((text or "").split())


def extract_confirmation_number(text):
    m = re.search(r"confirmation\s+number\s+is\s*:?\s*([A-Za-z0-9][A-Za-z0-9_\-]{4,})", text or "", re.I)
    return m.group(1).rstrip("-_") if m else ""


def _error_box_text(clean_text):
    """Text of the red 'Please correct the following errors' box, or ''."""
    low = clean_text.lower()
    start = low.find(_ERROR_HEADING)
    if start == -1:
        return ""
    start += len(_ERROR_HEADING)
    end = low.find("removal request (", start)          # legend of the form below the box
    if end == -1:
        end = start + 300
    return clean_text[start:end].strip(" :")


def classify_response(page_text):
    text = _clean(page_text)
    low = text.lower()
    if not text:
        return Result(ERROR, "", "The page was empty.")

    # Success page: request accepted -> the IP was listed as poor.
    number = extract_confirmation_number(text)
    if number or "request received" in low:
        msg = "Removal request submitted." if number else "Request received, but no confirmation number was found on the page."
        return Result(LISTED, number, msg)

    box = _error_box_text(text)
    if box:
        box_low = box.lower()
        if "not listed" in box_low:
            return Result(NOT_LISTED, "", NOT_LISTED_MESSAGE)
        if any(w in box_low for w in _DUPLICATE_WORDS):
            return Result(DUPLICATE, "", box)
        return Result(ERROR, "", box)

    if any(w in low for w in _BLOCK_WORDS):
        return Result(BLOCKED, "", "Barracuda showed a CAPTCHA / access-denied / rate-limit page.")

    return Result(ERROR, "", "Unrecognised page after submitting the form.")


def looks_like_response(page_text):
    """True once the page contains one of Barracuda's real answers (success, error box, or block page)."""
    text = _clean(page_text)
    low = text.lower()
    if not text:
        return False
    return bool(extract_confirmation_number(text) or "request received" in low
                or _ERROR_HEADING in low or any(w in low for w in _BLOCK_WORDS))
