"""Phase 5 boundary validation: proves the agent/tool stack cannot leak
evaluation truth. Reuses Phase 4's methodology (validate_graph.py) applied
to the new agent_v2 package, plus tool-layer-specific checks the spec calls
for explicitly (section 42/43).

Usage:
    python3 -m agent.agent_v2.validate_boundaries
"""
import ast
import re
import sys
from pathlib import Path

from agent.graph_v2 import checksums
from agent.graph_v2.db import get_driver
from agent.graph_v2.validate_graph import BANNED_SUBSTRINGS

AGENT_V2_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = AGENT_V2_DIR.parent / "graph_v2" / "manifests" / "dataset_classification.json"

WRITE_KEYWORDS = re.compile(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", re.IGNORECASE)

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  ok:   {msg}")


def _non_docstring_string_literals(path: Path):
    tree = ast.parse(path.read_text())
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids
    ]


def _all_string_literals(path: Path):
    tree = ast.parse(path.read_text())
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def check_no_eval_store_import():
    print("\n[1] agent_v2 never imports data.eval.eval_store")
    py_files = list(AGENT_V2_DIR.glob("*.py"))
    hits = []
    for p in py_files:
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "eval_store" in alias.name or alias.name.startswith("data.eval"):
                        hits.append((p.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "eval_store" in mod or mod.startswith("data.eval"):
                    hits.append((p.name, mod))
    if hits:
        for pyfile, mod in hits:
            fail(f"{pyfile} imports {mod}")
    else:
        ok(f"none of {len(py_files)} agent_v2/*.py files import data.eval.eval_store")


def check_no_eval_only_filenames():
    print("\n[2] agent_v2 source never references an evaluation_only/excluded_redundant filename")
    import json

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    eval_only_files = [
        fname
        for phase in ("phase1", "phase2", "phase3")
        for fname, entry in manifest[phase].items()
        if entry["bucket"] in ("evaluation_only", "excluded_redundant")
    ]
    hits = []
    for p in AGENT_V2_DIR.glob("*.py"):
        for literal in _non_docstring_string_literals(p):
            for fname in eval_only_files:
                if literal == fname or literal.endswith("/" + fname):
                    hits.append((p.name, fname, literal))
    if hits:
        for pyfile, fname, literal in hits:
            fail(f"{pyfile} references '{fname}' in a non-docstring literal: {literal!r}")
    else:
        ok(f"none of {len(eval_only_files)} evaluation_only/excluded_redundant filenames appear in agent_v2 source")


def check_tool_cypher_read_only():
    print("\n[3] Every tool's Cypher is read-only (no CREATE/MERGE/SET/DELETE/REMOVE/DETACH)")
    tools_path = AGENT_V2_DIR / "tools.py"
    hits = []
    for literal in _all_string_literals(tools_path):
        if "MATCH" in literal or "RETURN" in literal:  # looks like Cypher
            m = WRITE_KEYWORDS.search(literal)
            if m:
                hits.append((m.group(0), literal[:120]))
    if hits:
        for kw, snippet in hits:
            fail(f"tools.py contains write keyword '{kw}' in a Cypher-shaped string: {snippet!r}")
    else:
        ok("no write keyword found in any Cypher-shaped string literal in tools.py")


def check_tool_result_field_names():
    """Scans what TOOLS RETURN (observable evidence handed to the agent) for
    banned substrings -- NOT the agent's own FinalDiagnosis output schema.
    FinalDiagnosis fields like predicted_causal_change_id / root_cause_confidence
    are the agent's own inferred conclusion (exactly what spec sections 21/29
    ask it to produce) and legitimately contain words like "causal"/"root_cause" --
    that is not a leak, it's the deliverable. A leak would be a *tool result*
    field telling the agent which evidence is objectively causal/correct/
    distractor before it has inferred anything.
    """
    print("\n[4] No TOOL RESULT field name matches the banned-substring list (agent's own output schema is exempt)")
    tools_path = AGENT_V2_DIR / "tools.py"
    tree = ast.parse(tools_path.read_text())
    hits = []
    for node in ast.walk(tree):
        # Cypher "... AS alias" aliases
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and " AS " in node.value:
            for alias in re.findall(r"AS\s+(\w+)", node.value):
                low = alias.lower()
                for sub in BANNED_SUBSTRINGS:
                    if sub in low:
                        hits.append((alias, sub))
        # Python dict literal keys used to build tool results, e.g. {"signals": ...}
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    low = key.value.lower()
                    for sub in BANNED_SUBSTRINGS:
                        if sub in low:
                            hits.append((key.value, sub))
    if hits:
        for name, sub in sorted(set(hits)):
            fail(f"tools.py result field '{name}' matches banned substring '{sub}'")
    else:
        ok("no tool-result field name matches the banned-substring list")


def check_time_travel_through_tools():
    print("\n[5] Time-travel re-test through the tool layer (not raw Cypher)")
    from agent.agent_v2.time_gate import SimClock
    from agent.agent_v2.tools import q_active_incidents, q_recent_changes, q_technical_signals

    driver = get_driver()
    try:
        with driver.session() as session:
            case_id = "CS00191"
            clock = SimClock("2024-10-11")
            # The real policy-change (CH030460, started_at 2024-10-10 23:26) and the
            # real signal (SG0000943, timestamp 2024-10-10 22:37) both predate the
            # case's created_date -- so as_of == created_date should already see them
            # (they happened before investigation started), but an EARLIER as_of must not.
            before = q_recent_changes(session, case_id, "2024-10-10 20:00:00")
            after = q_recent_changes(session, case_id, clock.as_of)
            before_ids = {c["evidence_id"] for c in before["recent_changes"]}
            after_ids = {c["evidence_id"] for c in after["recent_changes"]}
            if "CH030460" in before_ids:
                fail("get_recent_changes leaked CH030460 (started_at 23:26) at an as_of of 20:00 the prior day")
            elif "CH030460" not in after_ids:
                fail("get_recent_changes did not surface CH030460 even at the case's own created_date -- unexpected")
            else:
                ok("get_recent_changes: CH030460 hidden before its own timestamp, visible after")

            sig_before = q_technical_signals(session, case_id, "2024-10-10 20:00:00")
            sig_after = q_technical_signals(session, case_id, clock.as_of)
            sig_before_ids = {s["evidence_id"] for s in sig_before["signals"]}
            sig_after_ids = {s["evidence_id"] for s in sig_after["signals"]}
            if "SG0000943" in sig_before_ids:
                fail("get_technical_signals leaked SG0000943 before its own timestamp")
            elif "SG0000943" not in sig_after_ids:
                fail("get_technical_signals did not surface SG0000943 even at the case's own created_date")
            else:
                ok("get_technical_signals: SG0000943 hidden before its own timestamp, visible after")

            inc = q_active_incidents(session, case_id, "1900-01-01 00:00:00")
            if inc["incidents"]:
                fail("get_active_incidents returned incidents at an impossibly early as_of")
            else:
                ok("get_active_incidents: correctly empty at an impossibly early as_of")
    finally:
        driver.close()


def run():
    FAILS.clear()
    checksums.verify_or_die()
    check_no_eval_store_import()
    check_no_eval_only_filenames()
    check_tool_cypher_read_only()
    check_tool_result_field_names()
    check_time_travel_through_tools()

    print("\n" + "=" * 70)
    if FAILS:
        print(f"BOUNDARY VALIDATION FAILED: {len(FAILS)} problem(s)")
        sys.exit(1)
    else:
        print("BOUNDARY VALIDATION PASSED: all checks green")


if __name__ == "__main__":
    run()
