import sqlite3
from datetime import datetime
from pathlib import Path


def now_str():
    """Local timestamp, e.g. 2026-10-18 14:03:27"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LogDatabase:
    COLUMNS = ("started_at", "completed_at", "ip_address", "status", "confirmation_number", "message")

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS request_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    ip_address TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confirmation_number TEXT DEFAULT '',
                    message TEXT DEFAULT ''
                )"""
            )

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def add_log(self, job_id, ip_address, started_at, completed_at, status, confirmation_number="", message=""):
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO request_logs
                       (job_id, started_at, completed_at, ip_address, status, confirmation_number, message)
                       VALUES (?,?,?,?,?,?,?)""",
                    (job_id, started_at, completed_at, ip_address, status, confirmation_number, message),
                )
        finally:
            conn.close()

    def get_job(self, job_id):
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM request_logs WHERE job_id=? ORDER BY log_id", (job_id,))]
        finally:
            conn.close()

    def all_logs(self, query="", limit=5000):
        conn = self._connect()
        try:
            if query.strip():
                q = f"%{query.strip()}%"
                rows = conn.execute(
                    """SELECT * FROM request_logs
                       WHERE ip_address LIKE ? OR status LIKE ? OR confirmation_number LIKE ? OR message LIKE ?
                       ORDER BY log_id DESC LIMIT ?""", (q, q, q, q, limit))
            else:
                rows = conn.execute("SELECT * FROM request_logs ORDER BY log_id DESC LIMIT ?", (limit,))
            return [dict(r) for r in rows]
        finally:
            conn.close()
