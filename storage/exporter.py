import csv
from pathlib import Path

CSV_FIELDS = ["ip_address", "status", "confirmation_number", "message", "started_at", "completed_at"]


def append_row(path, row):
    """Append one result to the CSV (header is written when the file is new)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_file = not p.exists()
    with p.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow(row)


def export_rows(rows, destination):
    """Write rows to a fresh CSV at destination and return the path."""
    p = Path(destination)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return p
