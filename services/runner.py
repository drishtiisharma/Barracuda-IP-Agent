"""
Background worker: takes the list of IPs and runs them one after another.
It never touches the UI directly - it only puts events on a queue.

Events:  ("status", text)  ("row", row_dict)  ("fatal", text)  ("done", "Finished"|"Stopped"|"Halted")
"""
import random
import threading
import time

from config.settings import DELAY_MIN_SECONDS, DELAY_MAX_SECONDS, MAX_CONSECUTIVE_ERRORS
from services.classification import Result, INVALID, DUPLICATE, ERROR, BLOCKED
from storage.database import now_str
from storage.exporter import append_row


class BatchRunner(threading.Thread):
    def __init__(self, job_id, valid, invalid, duplicates, db, csv_path, events, client_factory,
                 delay_range=(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS), sleep=time.sleep):
        super().__init__(daemon=True)
        self.job_id, self.valid, self.invalid, self.duplicates = job_id, valid, invalid, duplicates
        self.db, self.csv_path, self.events = db, csv_path, events
        self.client_factory = client_factory
        self.delay_range = delay_range
        self.sleep = sleep
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

    # ---- controls used by the UI
    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
        else:
            self.pause_event.set()
        return self.pause_event.is_set()

    # ---- internals
    def _record(self, ip, started, status, confirmation="", message=""):
        row = {"job_id": self.job_id, "ip_address": ip, "started_at": started, "completed_at": now_str(),
               "status": status, "confirmation_number": confirmation, "message": message}
        self.db.add_log(**row)
        append_row(self.csv_path, row)
        self.events.put(("row", row))

    def _wait_while_paused(self):
        while self.pause_event.is_set() and not self.stop_event.is_set():
            self.sleep(0.2)

    def _human_delay(self):
        seconds = random.uniform(*self.delay_range)       # a fresh random value every time
        end = time.monotonic() + seconds
        self.events.put(("status", f"Waiting {seconds:.1f}s before the next IP..."))
        while time.monotonic() < end and not self.stop_event.is_set():
            self._wait_while_paused()
            self.sleep(0.1)

    def run(self):
        client = None
        state = "Finished"
        try:
            for ip in self.invalid:
                t = now_str()
                self._record(ip, t, INVALID, "", "Not a valid IP address.")
            for ip in self.duplicates:
                t = now_str()
                self._record(ip, t, DUPLICATE, "", "Same IP appeared more than once in the input; skipped.")

            if self.valid:
                client = self.client_factory(lambda m: self.events.put(("status", m)), self.stop_event.is_set)
                errors_in_a_row = 0
                last = len(self.valid) - 1
                for i, ip in enumerate(self.valid):
                    self._wait_while_paused()
                    if self.stop_event.is_set():
                        state = "Stopped"
                        break
                    started = now_str()
                    self.events.put(("status", f"IP {i + 1}/{len(self.valid)}: {ip}"))
                    try:
                        result = client.check_ip(ip)
                    except Exception as exc:                          # noqa: BLE001
                        client.invalidate()
                        if self.stop_event.is_set():
                            self._record(ip, started, ERROR, "", str(exc)[:300])
                            state = "Stopped"
                            break
                        result = Result(ERROR, "", f"{type(exc).__name__}: {str(exc)[:300]}".replace("\n", " "))
                    self._record(ip, started, result.status, result.confirmation_number, result.message)

                    if result.status == BLOCKED:
                        self.events.put(("status", result.message + " Batch halted."))
                        state = "Halted"
                        break
                    errors_in_a_row = errors_in_a_row + 1 if result.status == ERROR else 0
                    if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                        self.events.put(("status", f"{errors_in_a_row} errors in a row. Batch halted."))
                        state = "Halted"
                        break
                    if i < last:
                        self._human_delay()
        except Exception as exc:                                      # noqa: BLE001
            self.events.put(("fatal", str(exc)))
            state = "Halted"
        finally:
            if client:
                try:
                    client.close()
                except Exception:                                     # noqa: BLE001
                    pass
            self.events.put(("done", state))
