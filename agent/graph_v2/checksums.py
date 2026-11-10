"""Phase 4 input-manifest verification.

Phase 4 must never proceed against Phase 1/2/3 data that has drifted from
what was validated and frozen. This module owns Phase 4's *own* baseline
snapshot (independent of data/generators_phase3's internal checksums, which
belong to Phase 3's own build) and fails fast on any mismatch.

Usage:
    python3 -m agent.graph_v2.checksums --bootstrap   # one-time: snapshot current files
    python3 -m agent.graph_v2.checksums                # verify (default)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"

PHASES = {
    "phase1": PROJECT_ROOT / "data" / "raw_v2",
    "phase2": PROJECT_ROOT / "data" / "phase2",
    "phase3": PROJECT_ROOT / "data" / "phase3",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest(data_dir: Path) -> dict:
    manifest = {}
    for path in sorted(data_dir.glob("*.csv")):
        manifest[path.name] = sha256_file(path)
    return manifest


def bootstrap():
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    for phase, data_dir in PHASES.items():
        manifest = compute_manifest(data_dir)
        out_path = MANIFEST_DIR / f"{phase}_checksums.json"
        with open(out_path, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        print(f"  wrote {out_path.relative_to(PROJECT_ROOT)}  ({len(manifest)} files)")


def verify() -> list:
    """Returns a list of (phase, filename, reason) mismatches. Empty = clean."""
    problems = []
    for phase, data_dir in PHASES.items():
        manifest_path = MANIFEST_DIR / f"{phase}_checksums.json"
        if not manifest_path.exists():
            problems.append((phase, "<manifest>", f"missing manifest file {manifest_path}"))
            continue
        with open(manifest_path) as f:
            expected = json.load(f)
        actual = compute_manifest(data_dir)
        for fname, expected_hash in expected.items():
            actual_hash = actual.get(fname)
            if actual_hash is None:
                problems.append((phase, fname, "file missing from data directory"))
            elif actual_hash != expected_hash:
                problems.append((phase, fname, "checksum mismatch — file has changed since Phase 4's baseline"))
        for fname in actual:
            if fname not in expected:
                problems.append((phase, fname, "new/unexpected file not in Phase 4's baseline manifest"))
    return problems


def verify_or_die():
    problems = verify()
    if problems:
        print("Phase 4 input-manifest verification FAILED:", file=sys.stderr)
        for phase, fname, reason in problems:
            print(f"  [{phase}] {fname}: {reason}", file=sys.stderr)
        print(
            "\nRefusing to proceed — Phase 1/2/3 data must remain frozen. "
            "If this drift is expected and approved, re-run with --bootstrap "
            "to accept the new baseline.",
            file=sys.stderr,
        )
        sys.exit(1)
    total = sum(len(json.load(open(MANIFEST_DIR / f"{p}_checksums.json"))) for p in PHASES)
    print(f"Phase 1/2/3 input manifests verified clean ({total} files, 0 mismatches).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true", help="snapshot current files as the new baseline")
    args = parser.parse_args()
    if args.bootstrap:
        bootstrap()
    else:
        verify_or_die()
