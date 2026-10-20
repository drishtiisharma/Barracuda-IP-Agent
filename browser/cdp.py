"""
Tiny, dependency-free way to drive Microsoft Edge / Google Chrome.

Instead of Playwright (whose Node.js driver alone is ~60 MB) we start the browser that is already
installed on the PC with a private temporary profile and talk to it over the Chrome DevTools
Protocol (a WebSocket on localhost). Only Python's standard library is used, which keeps the
packaged .exe very small.
"""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class CDPError(Exception):
    pass


# ----------------------------------------------------------------------------- browser discovery
def find_browser():
    """Path of Edge/Chrome/Chromium, or None. Set BARRACUDA_BROWSER to force a specific browser."""
    override = os.environ.get("BARRACUDA_BROWSER")
    if override and Path(override).exists():
        return override

    candidates = []
    if sys.platform.startswith("win"):
        for var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
            root = os.environ.get(var)
            if root:
                candidates += [
                    Path(root) / "Microsoft/Edge/Application/msedge.exe",
                    Path(root) / "Google/Chrome/Application/chrome.exe",
                ]
        try:                                              # also ask the registry (non-standard installs)
            import winreg
            for name in ("msedge.exe", "chrome.exe"):
                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}") as k:
                            candidates.append(Path(winreg.QueryValueEx(k, "")[0]))
                    except OSError:
                        pass
        except ImportError:
            pass
    elif sys.platform == "darwin":
        candidates += [
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    else:
        for name in ("microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

    for c in candidates:
        if c.exists():
            return str(c)
    return None


# ----------------------------------------------------------------------------- minimal WebSocket
class WebSocket:
    """Just enough of RFC 6455 to talk to the DevTools endpoint on localhost."""

    def __init__(self, port, path, timeout=30):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("Browser closed the connection during the WebSocket handshake.")
            data += chunk
        head, _, self.buf = data.partition(b"\r\n\r\n")
        if b" 101" not in head.split(b"\r\n", 1)[0]:
            raise CDPError("Browser refused the DevTools WebSocket: " + head.split(b"\r\n", 1)[0].decode(errors="replace"))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CDPError("Browser connection closed.")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send_frame(self, opcode, payload):
        n = len(payload)
        header = bytearray([0x80 | opcode])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text):
        self._send_frame(0x1, text.encode("utf-8"))

    def recv(self, timeout):
        self.sock.settimeout(timeout)
        message = b""
        while True:
            b1, b2 = self._read(2)
            fin, opcode, length = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(length)
            if opcode == 0x8:
                raise CDPError("Browser closed the DevTools connection.")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            message += payload
            if fin:
                return message.decode("utf-8")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class CDP:
    """Send a DevTools command, wait for its answer (events are ignored)."""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0

    def call(self, method, params=None, timeout=30):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.monotonic() + timeout
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise CDPError(f"{method}: no answer from the browser within {timeout}s")
            try:
                msg = json.loads(self.ws.recv(remaining))
            except socket.timeout:
                raise CDPError(f"{method}: no answer from the browser within {timeout}s")
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error'].get('message', msg['error'])}")
                return msg.get("result", {})

    def close(self):
        self.ws.close()


# ----------------------------------------------------------------------------- browser process
def _http_get_json(port, path, timeout=5):
    """GET a DevTools JSON endpoint. (Chrome keeps the connection open, so read exactly Content-Length bytes.)"""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        length = None
        for line in head.split(b"\r\n")[1:]:
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip())
        while length is not None and len(body) < length:
            chunk = s.recv(65536)
            if not chunk:
                break
            body += chunk
    return json.loads(body.decode("utf-8"))


class BrowserProcess:
    """A brand-new browser window with its own empty profile (= a completely fresh session)."""

    def __init__(self, exe, window_rect=None, startup_timeout=60):
        self.profile_dir = tempfile.mkdtemp(prefix="bcuda_profile_")
        args = [
            exe,
            "--remote-debugging-port=0",
            f"--user-data-dir={self.profile_dir}",
            "--remote-allow-origins=*",
            "--no-first-run", "--no-default-browser-check", "--disable-sync", "--disable-default-apps",
            # keep the page running at full speed even when other windows cover it
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-features=CalculateNativeWinOcclusion",
        ]
        if window_rect:
            x, y, w, h = window_rect
            args += [f"--window-position={x},{y}", f"--window-size={w},{h}"]
        args += os.environ.get("BARRACUDA_BROWSER_ARGS", "").split()      # for testing / advanced use
        args.append("about:blank")

        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        port_file = Path(self.profile_dir) / "DevToolsActivePort"
        end = time.monotonic() + startup_timeout
        while not port_file.exists() or len(port_file.read_text().split()) < 2:
            if self.proc.poll() is not None:
                self._cleanup()
                raise CDPError("The browser exited right after starting.")
            if time.monotonic() > end:
                self.close()
                raise CDPError("The browser did not start in time.")
            time.sleep(0.2)
        lines = port_file.read_text().split()
        self.port, self.browser_path = int(lines[0]), lines[1]
        self.cdp = None

    def alive(self):
        return self.proc.poll() is None

    def connect_page(self, timeout=30):
        """Attach to the first open tab and return a CDP object."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                pages = [t for t in _http_get_json(self.port, "/json/list") if t.get("type") == "page"]
            except (OSError, ValueError):
                pages = []
            if pages:
                path = "/" + pages[0]["webSocketDebuggerUrl"].split("/", 3)[3]
                self.cdp = CDP(WebSocket(self.port, path))
                return self.cdp
            time.sleep(0.3)
        raise CDPError("Could not find the browser tab to control.")

    def _cleanup(self):
        shutil.rmtree(self.profile_dir, ignore_errors=True)

    def close(self):
        try:
            if self.cdp:
                self.cdp.close()
        except Exception:                                  # noqa: BLE001
            pass
        try:
            if self.alive():                               # polite close first (closes every process)
                browser_cdp = CDP(WebSocket(self.port, self.browser_path, timeout=5))
                try:
                    browser_cdp.call("Browser.close", timeout=5)
                finally:
                    browser_cdp.close()
        except Exception:                                  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:                                  # noqa: BLE001
            try:
                self.proc.kill()
            except Exception:                              # noqa: BLE001
                pass
        time.sleep(0.5)
        self._cleanup()
