"""Shared CSV I/O helpers for the Phase 2 generator pipeline. Mirrors
data/generators/csv_io.py exactly, but targets data/phase2/ instead of
data/raw_v2/ so the two layers can never collide on output paths."""
import csv
import os

PHASE2_DIR = os.path.join(os.path.dirname(__file__), "..", "phase2")
os.makedirs(PHASE2_DIR, exist_ok=True)


def write_csv(filename, rows, headers):
    path = os.path.join(PHASE2_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓  {filename:<32} {len(rows):>9,} rows")


def read_csv(filename):
    path = os.path.join(PHASE2_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
