"""
Drives the Barracuda removal-request form in a VISIBLE Edge/Chrome window.

Flow per IP
-----------
* First IP of a session (or after the previous IP was LISTED and the site moved to the
  "Request Received" page): open the form and type ALL fields.
* If the previous IP was NOT LISTED, Barracuda re-shows the same form with the red box and
  our values still filled in. In that case ONLY the IP box is retyped - the rest is left alone,
  so we don't repeat the same full-form behaviour again and again.
* After SESSION_REFRESH_THRESHOLD IPs the whole browser window is closed and a new one opened.
* After pressing Submit we WAIT for Barracuda's real answer page (no fixed timeout).

The script never brings the window to the front, so it will not keep jumping over your work.
"""
import json
import random
import time

from browser.cdp import BrowserProcess, CDPError, find_browser
from config.settings import (
    REMOVAL_URL, SESSION_REFRESH_THRESHOLD, TYPING_DELAY_MS, REASON_TYPING_DELAY_MS,
    FIELD_PAUSE_SECONDS, PRE_SUBMIT_PAUSE_SECONDS, RESPONSE_TIMEOUT_SECONDS, PAGE_LOAD_TIMEOUT_SECONDS,
)
from services.classification import classify_response, looks_like_response, NOT_LISTED

# JavaScript helper placed in front of every snippet we run inside the page.
# __els() -> [ip, email, name, customer email, phone, reason textarea, submit button] or null
_PRELUDE = """
const __f = [...document.forms].find(f => f.querySelector('textarea'));
function __els() {
  if (!__f) return null;
  const skip = ['hidden','submit','button','image','checkbox','radio','reset'];
  const ins = [...__f.querySelectorAll('input')].filter(i => !skip.includes((i.type || 'text').toLowerCase()));
  if (ins.length < 5) return null;
  let sub = __f.querySelector('input[type=submit],button[type=submit]');
  if (!sub) sub = [...__f.querySelectorAll('input,button')].find(e => /submit/i.test(e.value || e.textContent || ''));
  return [ins[0], ins[1], ins[2], ins[3], ins[4], __f.querySelector('textarea'), sub];
}
"""

# While a page is loading the browser holds our scripts, so waiting loops poll with a short timeout.
# That keeps the status text updating and the Stop button responsive.
POLL_TIMEOUT = 2

IP_BOX, EMAIL_BOX, NAME_BOX, CUSTOMER_EMAIL_BOX, PHONE_BOX, REASON_BOX, SUBMIT_BTN = range(7)


class FormNotFound(Exception):
    pass


class StopWaiting(Exception):
    """The user pressed Stop while we were waiting for Barracuda."""


def _norm(text):
    return " ".join((text or "").split())


class BarracudaClient:
    def __init__(self, profile, window_rect=None, status_cb=None, should_stop=None):
        """
        profile      dict with email_address, customer_name, customer_email, phone_number, reason_for_removal
        window_rect  (x, y, width, height) in pixels for the browser window, or None
        status_cb    callable(str) used to tell the UI what is happening
        should_stop  callable() -> True when the user pressed Stop
        """
        self.profile = profile
        self.window_rect = window_rect
        self.say = status_cb or (lambda _msg: None)
        self.should_stop = should_stop or (lambda: False)
        self.proc = None             # BrowserProcess
        self.cdp = None              # DevTools connection to the open tab
        self.since_refresh = 0
        self.form_ready = False      # True when the form is on screen with our details still filled in
        self._reset_requested = False

    # ------------------------------------------------------------------ session
    def _open_session(self):
        """Close any old window and open a completely fresh one (empty profile = fresh session)."""
        self._close_browser_only()
        exe = find_browser()
        if not exe:
            raise RuntimeError(
                "Could not find Microsoft Edge or Google Chrome on this PC.\n"
                "Please install one of them and try again.")
        self.say("Opening a new browser window...")
        try:
            self.proc = BrowserProcess(exe, self.window_rect)
            self.cdp = self.proc.connect_page()
            try:                      # make the page behave as 'focused' even if another app is in front
                self.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
            except CDPError:
                pass
        except CDPError as exc:
            self._close_browser_only()
            raise RuntimeError(f"Could not start the browser: {exc}")
        self.since_refresh = 0
        self.form_ready = False
        self._reset_requested = False

    def _close_browser_only(self):
        if self.proc:
            try:
                self.proc.close()
            except Exception:                  # noqa: BLE001
                pass
        self.proc = self.cdp = None

    def close(self):
        self._close_browser_only()

    def invalidate(self):
        """Call after an unexpected error: next IP gets a fresh window and a fully filled form."""
        self.form_ready = False
        self._reset_requested = True

    def _browser_alive(self):
        return bool(self.proc and self.proc.alive())

    # ------------------------------------------------------------------ page helpers
    def _eval(self, body, timeout=20):
        """Run JavaScript (with the __els() helper available) and return its value."""
        expression = "(function(){" + _PRELUDE + body + "})()"
        result = self.cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=timeout)
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            text = (details.get("exception") or {}).get("description") or details.get("text", "script error")
            raise CDPError(text)
        return result.get("result", {}).get("value")

    @staticmethod
    def _pause(rng):
        time.sleep(random.uniform(*rng))

    def _check_stop(self):
        if self.should_stop():
            raise StopWaiting("Stopped by the user; the request may or may not have been processed.")

    def _click(self, index):
        """Real mouse click on one of the form elements (at a slightly random spot inside it)."""
        point = self._eval(
            f"const e = __els()[{index}]; e.scrollIntoView({{block: 'center'}});"
            "const r = e.getBoundingClientRect();"
            "return {x: r.left + r.width * (0.2 + 0.6 * Math.random()), y: r.top + r.height * (0.3 + 0.4 * Math.random())};")
        if not point:
            raise FormNotFound("Could not find the removal form on the page.")
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.cdp.call("Input.dispatchMouseEvent", {
                "type": kind, "x": point["x"], "y": point["y"], "button": "left" if kind != "mouseMoved" else "none",
                "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 0 if kind == "mouseMoved" else 1})
            time.sleep(random.uniform(0.03, 0.09))

    def _press_key(self, ch):
        if ch == "\n":
            params = {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}
        else:
            params = {"key": ch, "text": ch, "unmodifiedText": ch}
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **params})
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": params["key"]})

    def _type_into(self, index, text, delay_range, per_key_random=True):
        self._click(index)
        self._eval(f"const e = __els()[{index}]; e.focus(); e.value = ''; e.dispatchEvent(new Event('input', {{bubbles: true}}));")
        fixed = random.randint(*delay_range)
        for ch in text:
            self._press_key(ch)
            time.sleep((random.randint(*delay_range) if per_key_random else fixed) / 1000.0)
        # Safety net: if the browser swallowed a key (e.g. it was busy), make sure the box holds the right text.
        self._eval(
            f"const e = __els()[{index}]; const want = {json.dumps(text)};"
            "if (e.value !== want) { e.value = want; e.dispatchEvent(new Event('input', {bubbles: true}));"
            " e.dispatchEvent(new Event('change', {bubbles: true})); }")

    def _goto_form(self):
        self.say("Opening the removal-request page...")
        try:
            self._eval("window.__bcMarker = true;")        # lets us tell when the NEW page has replaced this one
        except CDPError:
            pass
        self.cdp.call("Page.navigate", {"url": REMOVAL_URL})
        end = time.monotonic() + PAGE_LOAD_TIMEOUT_SECONDS
        while True:
            self._check_stop()
            if time.monotonic() > end:
                raise TimeoutError(f"The removal-request page did not load within {PAGE_LOAD_TIMEOUT_SECONDS} seconds.")
            time.sleep(0.4)
            try:
                if (not self._eval("return window.__bcMarker === true;", timeout=POLL_TIMEOUT)
                        and self._eval("return !!__els();", timeout=POLL_TIMEOUT)):
                    break
            except CDPError:
                continue                                    # page is mid-navigation (the browser holds scripts until it is done)
        self._pause(FIELD_PAUSE_SECONDS)

    def _fill_all(self, ip):
        p = self.profile
        values = [(IP_BOX, ip), (EMAIL_BOX, p["email_address"]), (NAME_BOX, p["customer_name"]),
                  (CUSTOMER_EMAIL_BOX, p["customer_email"]), (PHONE_BOX, p["phone_number"])]
        for index, value in values:
            self._type_into(index, value, TYPING_DELAY_MS)
            self._pause(FIELD_PAUSE_SECONDS)
        self._type_into(REASON_BOX, p["reason_for_removal"], REASON_TYPING_DELAY_MS, per_key_random=False)

    def _fill_ip_only(self, ip):
        self.say(f"Same form still open - only updating the IP to {ip}")
        self._type_into(IP_BOX, ip, TYPING_DELAY_MS)

    def _other_fields_intact(self):
        """True if the form on screen still holds our profile values (everything except the IP)."""
        try:
            p = self.profile
            values = self._eval("const e = __els(); return e ? [e[1].value, e[2].value, e[3].value, e[4].value, e[5].value] : null;")
            if not values:
                return False
            expected = [p["email_address"], p["customer_name"], p["customer_email"], p["phone_number"], p["reason_for_removal"]]
            return all(_norm(a) == _norm(b) for a, b in zip(values, expected))
        except Exception:                      # noqa: BLE001
            return False

    def _submit(self):
        """
        Press Submit Request, then WAIT until Barracuda's real answer page has arrived and return its text.
        There is no fixed timeout (unless RESPONSE_TIMEOUT_SECONDS is set); Stop cancels the wait.
        """
        self._eval("window.__bcMarker = true;")             # tag the current document
        self._click(SUBMIT_BTN)

        started = time.monotonic()
        last_say = 0.0
        unrecognised_since = None
        while True:
            self._check_stop()
            waited = time.monotonic() - started
            if RESPONSE_TIMEOUT_SECONDS and waited > RESPONSE_TIMEOUT_SECONDS:
                raise TimeoutError(f"No response from Barracuda after {int(waited)} seconds.")
            if waited - last_say >= 5:
                last_say = waited
                self.say(f"Waiting for Barracuda's response... {int(waited)}s")
            time.sleep(0.5)
            try:
                if self._eval("return window.__bcMarker === true;", timeout=POLL_TIMEOUT):
                    continue                    # still the old page; the response is not here yet
                text = self._eval("return document.body ? document.body.innerText : '';", timeout=POLL_TIMEOUT)
            except CDPError:                    # the browser holds scripts while the new page loads - keep waiting
                continue
            if looks_like_response(text):
                time.sleep(0.4)                 # let the page finish rendering, then read it once more
                try:
                    text = self._eval("return document.body ? document.body.innerText : '';", timeout=10) or text
                except CDPError:
                    pass
                return text
            # A new page arrived but it is not one we recognise. Give it a while to finish loading.
            unrecognised_since = unrecognised_since or time.monotonic()
            if time.monotonic() - unrecognised_since > 30:
                return text

    # ------------------------------------------------------------------ public
    def check_ip(self, ip):
        """Submit one IP through the removal form and return a classification.Result."""
        if (self.cdp is None or self._reset_requested or not self._browser_alive()
                or self.since_refresh >= SESSION_REFRESH_THRESHOLD):
            self._open_session()

        if self.form_ready and self._other_fields_intact():
            self._fill_ip_only(ip)
        else:
            self._goto_form()
            self.say(f"Filling the form for {ip}")
            self._fill_all(ip)

        self._pause(PRE_SUBMIT_PAUSE_SECONDS)
        self.say(f"Submitting {ip}")
        text = self._submit()
        self.since_refresh += 1

        result = classify_response(text)
        # Only a "not listed" answer leaves the filled form on screen for reuse.
        self.form_ready = result.status == NOT_LISTED
        return result
