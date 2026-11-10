"""Shared CSV I/O helpers for the Phase 1 generator pipeline."""
import csv
import os

RAW = os.path.join(os.path.dirname(__file__), "..", "raw_v2")
os.makedirs(RAW, exist_ok=True)


def write_csv(filename, rows, headers):
    path = os.path.join(RAW, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓  {filename:<32} {len(rows):>8,} rows")


def read_csv(filename):
    path = os.path.join(RAW, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
