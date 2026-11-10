"""One-off: capture SHA-256 baselines for Phase 1 and Phase 2 CSVs before any
Phase 3 code runs. Mirrors generators_phase2/.phase1_checksums.json."""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_V1 = os.path.join(HERE, "..", "raw_v2")
PHASE2 = os.path.join(HERE, "..", "phase2")


def manifest(directory):
    out = {}
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".csv"):
            with open(os.path.join(directory, fn), "rb") as f:
                out[fn] = hashlib.sha256(f.read()).hexdigest()
    return out


if __name__ == "__main__":
    with open(os.path.join(HERE, ".phase1_checksums.json"), "w") as f:
        json.dump(manifest(RAW_V1), f, indent=2, sort_keys=True)
    with open(os.path.join(HERE, ".phase2_checksums.json"), "w") as f:
        json.dump(manifest(PHASE2), f, indent=2, sort_keys=True)
    print("Wrote checksum baselines for", len(os.listdir(RAW_V1)), "raw_v2 files and",
          len(os.listdir(PHASE2)), "phase2 files.")
