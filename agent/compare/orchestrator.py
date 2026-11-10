"""Runs the three architectures. The boundaries are structural, not cosmetic:
  LLM Only        a ticket load + one direct model call. No backend is built, no tool is executed, no Jev client is touched.
  LLM + Graph     the agent loop with `verifier=None`: Neo4j tools yes, verification and Jev never.
  LLM + Graph+Jev early Jev triage (a provisional category hint from the ticket text, guidance only) + the agent + the Phase 9 late verifier (deterministic checks, three Jev
                  signals, policy, optional extra round). Two Jev roles: early = triage guidance, late = answer verification.
Every run is persisted so it can be reopened without an API call. Dev cases only. This module imports no evaluation code and no ground truth."""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.agent_v3.backend import Neo4jBackend
from agent.agent_v3.config import PROJECT_ROOT
from agent.agent_v3.loop import run_case
from agent.agent_v3.trace import persist_run
from agent.compare import adapters, llm_only
from agent.compare.models import MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, ComparisonResult
from agent.compare.ticket import load_ticket
from agent.runtime_verifier.run import persist as persist_verified
from agent.runtime_verifier.run import run_verified_case

FALLBACK_COST = {MODE_LLM: 0.002, MODE_GRAPH: 0.02, MODE_FULL: 0.03}


def assert_dev(case_id: str) -> None:
    pool = json.loads((PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"]
    if case_id not in pool:
        raise ValueError(f"{case_id} is not a dev case")


def run_mode(mode: str, case_id: str, *, session_factory, llm, jev_client=None, backend_factory=Neo4jBackend, ticket_loader=load_ticket, save: bool = True) -> ComparisonResult:
    assert_dev(case_id)
    if mode == MODE_LLM:
        with session_factory() as session:
            ticket = ticket_loader(session, case_id)          # the case record only; the session is closed before the model is called
        record = llm_only.run_llm_only(case_id, ticket, llm)
        if save:
            llm_only.persist(record)
        return adapters.from_llm_only(record, "live")
    if mode == MODE_GRAPH:
        with session_factory() as session:
            run = run_case(case_id, backend_factory(session, case_id), llm)          # verifier=None: Jev can never be reached
        if save:
            run = json.loads(persist_run(run, "ui").read_text())
        return adapters.from_graph_run(run, "live")
    if mode == MODE_FULL:
        with session_factory() as session:
            record = run_verified_case(case_id, session, llm, jev_client, backend=backend_factory(session, case_id), early_triage=True)
        if save:
            record = json.loads(persist_verified(record).read_text())
        return adapters.from_verified(record, "live")
    raise ValueError(f"unknown mode {mode!r}")


def run_modes(modes, case_id: str, *, session_factory, llm, jev_client=None, on_update=None, parallel: bool = True, **kw) -> dict:
    """{mode: ComparisonResult | Exception}. The three modes are independent, so they run in parallel; `on_update(mode, state, payload)` is called on the calling thread
    ('started' for each, then 'done' or 'error' as each finishes) so a UI can show progress."""
    modes, out = list(modes), {}
    notify = on_update or (lambda *a: None)
    for m in modes:
        notify(m, "started", None)
    if not parallel:
        for m in modes:
            t0 = time.time()
            try:
                out[m] = run_mode(m, case_id, session_factory=session_factory, llm=llm, jev_client=jev_client, **kw)
                notify(m, "done", out[m])
            except Exception as e:  # noqa: BLE001 - surfaced to the caller per mode
                out[m] = e
                notify(m, "error", e)
        return out
    with ThreadPoolExecutor(max_workers=max(1, len(modes))) as ex:
        futs = {ex.submit(run_mode, m, case_id, session_factory=session_factory, llm=llm, jev_client=jev_client, **kw): m for m in modes}
        for f in as_completed(futs):
            m = futs[f]
            try:
                out[m] = f.result()
                notify(m, "done", out[m])
            except Exception as e:  # noqa: BLE001
                out[m] = e
                notify(m, "error", e)
    return out


def cost_estimate(modes) -> dict:
    """Estimated cost per mode: the mean of up to 20 stored runs of that mode, else a fallback constant. Rounded; an estimate, not a quote."""
    per = {}
    for m in modes:
        vals = []
        for cid in list({MODE_LLM: adapters.llm_index, MODE_GRAPH: adapters.graph_index, MODE_FULL: adapters.full_index}[m]())[:20]:
            r = adapters.load_stored(m, cid)
            if r:
                vals.append(r.estimated_cost)
        per[m] = {"cost": (sum(vals) / len(vals)) if vals else FALLBACK_COST[m], "basis": len(vals)}
    return {"per_mode": per, "total": sum(v["cost"] for v in per.values())}
