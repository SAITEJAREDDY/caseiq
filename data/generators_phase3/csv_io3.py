"""Shared CSV I/O helpers for the Phase 3 generator pipeline. Mirrors
data/generators_phase2/csv_io2.py, but targets data/phase3/."""
import csv
import os

PHASE3_DIR = os.path.join(os.path.dirname(__file__), "..", "phase3")
os.makedirs(PHASE3_DIR, exist_ok=True)


def write_csv(filename, rows, headers):
    path = os.path.join(PHASE3_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓  {filename:<36} {len(rows):>9,} rows")


def read_csv(filename):
    path = os.path.join(PHASE3_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
