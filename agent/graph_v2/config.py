"""Phase 4's own Neo4j credentials -- a SEPARATE AuraDB instance from the one
the live app uses (config/settings.py's NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD).

Uses os.getenv (optional), not os.environ[...], so a fresh checkout without
NEO4J_V2_* set doesn't break importing this module -- unlike config/settings.py,
which is never imported here and never imports this.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

NEO4J_V2_URI = os.getenv("NEO4J_V2_URI", "").strip() or None
NEO4J_V2_USERNAME = os.getenv("NEO4J_V2_USERNAME", "").strip() or None
NEO4J_V2_PASSWORD = os.getenv("NEO4J_V2_PASSWORD", "").strip() or None

DATA_RAW_V2 = PROJECT_ROOT / "data" / "raw_v2"
DATA_PHASE2 = PROJECT_ROOT / "data" / "phase2"
DATA_PHASE3 = PROJECT_ROOT / "data" / "phase3"

BATCH = 500  # rows per transaction, matches agent/neo4j_loader.py


def require_credentials():
    missing = [
        name
        for name, val in [
            ("NEO4J_V2_URI", NEO4J_V2_URI),
            ("NEO4J_V2_USERNAME", NEO4J_V2_USERNAME),
            ("NEO4J_V2_PASSWORD", NEO4J_V2_PASSWORD),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing Phase 4 Neo4j credentials in .env: "
            + ", ".join(missing)
            + ". Create a separate AuraDB instance for the Phase 4 runtime "
            "graph (do not reuse the live app's NEO4J_URI) and add these "
            "three vars."
        )
