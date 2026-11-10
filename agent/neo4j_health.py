"""Health check for CaseIQ's two hosted Neo4j (Aura) databases:

  live app graph       NEO4J_*     the Phase 0 demo graph the main chat page reads
  Phase 4 agent graph  NEO4J_V2_*  the runtime graph the Diagnostic Agent page reads

These are cloud instances, so there is nothing local to start. What this does: resolve the host, connect, run a trivial query (which also counts as activity, so Aura Free does not
pause the instance for inactivity while you use the app), and say precisely what is wrong when a database is not reachable. It never writes to a graph.

    python3 -m agent.neo4j_health             # status table; exit code 0 only if both are reachable
    python3 -m agent.neo4j_health --counts    # also node and relationship counts
    python3 -m agent.neo4j_health --wait 120  # retry for up to 120 s (e.g. right after resuming an instance in the console)
"""
import argparse
import os
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATABASES = (("Live app graph", "NEO4J"), ("Phase 4 agent graph", "NEO4J_V2"))
CONSOLE = "console.neo4j.io"
RELOAD = {"NEO4J": "reload the demo data with `python3 agent/neo4j_loader.py` (idempotent, about 15 s)",
          "NEO4J_V2": "rebuild the graph with `python3 -m agent.graph_v2.build_graph --mode small --wipe`"}


def unresolved_hint(prefix: str) -> str:
    return (f"The Aura hostname does not resolve. For Aura Free this almost always means the instance is PAUSED (a paused instance's hostname stops resolving; its data is kept): open {CONSOLE}, "
            "resume it, wait about a minute, then re-check. Only if it stayed paused for about 30 days is it deleted; then create a new free instance, put its URI, username and password in .env as "
            f"{prefix}_URI / {prefix}_USERNAME / {prefix}_PASSWORD, and {RELOAD[prefix]}.")


PAUSED = (f"The instance did not answer. Aura Free instances pause after about 3 days without a query; open {CONSOLE}, resume it (about a minute), then re-check. "
          "Starting the app or opening a page while it is running counts as activity.")


def _host(uri: str) -> str:
    return re.sub(r"^[^:]+://", "", uri.strip()).split(":")[0].split("/")[0]


def check(name: str, prefix: str, counts: bool = False, timeout: float = 8.0) -> dict:
    load_dotenv(ROOT / ".env")
    uri, user, pw = (os.environ.get(f"{prefix}_{k}", "").strip() for k in ("URI", "USERNAME", "PASSWORD"))
    out = {"name": name, "prefix": prefix, "ok": False, "state": "", "summary": "", "hint": "", "latency_s": None, "nodes": None, "relationships": None}
    if not (uri and user and pw):
        return {**out, "state": "not_configured", "summary": "not configured", "hint": f"Set {prefix}_URI, {prefix}_USERNAME and {prefix}_PASSWORD in .env (see .env.example)."}
    try:
        socket.getaddrinfo(_host(uri), 7687)
    except socket.gaierror:
        return {**out, "state": "unresolved", "summary": "host not found (paused?)", "hint": unresolved_hint(prefix)}
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable
    t0 = time.time()
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pw), connection_timeout=timeout)
        try:
            with driver.session() as s:
                s.run("RETURN 1").consume()
                if counts:
                    out["nodes"] = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                    out["relationships"] = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        finally:
            driver.close()
    except AuthError:
        return {**out, "state": "auth", "summary": "login rejected", "hint": f"The username or password for {prefix}_* in .env is wrong (or the instance was recreated with a new password)."}
    except ServiceUnavailable:
        return {**out, "state": "paused", "summary": "not answering (paused?)", "hint": PAUSED}
    except Exception as e:  # noqa: BLE001 - reported, never hidden
        return {**out, "state": "error", "summary": f"{type(e).__name__}", "hint": str(e)[:200]}
    out.update(ok=True, state="ok", latency_s=round(time.time() - t0, 2), summary="connected" + (f", {out['nodes']:,} nodes / {out['relationships']:,} relationships" if counts else ""))
    return out


def check_all(counts: bool = False) -> list:
    with ThreadPoolExecutor(max_workers=len(DATABASES)) as ex:
        return list(ex.map(lambda d: check(d[0], d[1], counts), DATABASES))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--wait", type=int, default=0, help="keep re-checking for up to this many seconds until both are reachable")
    a = ap.parse_args()
    deadline = time.time() + a.wait
    while True:
        results = check_all(a.counts)
        if all(r["ok"] for r in results) or time.time() >= deadline:
            break
        time.sleep(5)
    for r in results:
        print(f"  {'✅' if r['ok'] else '❌'} {r['name']:20s} {r['summary']}" + (f" ({r['latency_s']}s)" if r["latency_s"] else ""))
        if not r["ok"]:
            print(f"       {r['hint']}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
