"""
CaseIQ eval results viewer.
Run: streamlit run evals_dashboard.py --server.port 8504
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
EVAL_RUNS_DIR = PROJECT_ROOT / "data" / "eval_runs"

st.set_page_config(
    page_title="CaseIQ Evals",
    page_icon="✅",
    layout="wide",
)

st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: #0f172a !important; font-size: 28px !important; font-weight: 800 !important; }
.eval-header {
    padding: 24px 0 10px;
}
.eval-brand {
    font-size: 36px;
    font-weight: 900;
    color: #0f172a;
}
.eval-subtitle {
    color: #64748b;
    font-size: 13px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 6px;
}
.status-pass {
    color: #15803d;
    font-weight: 800;
}
.status-fail {
    color: #b91c1c;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)


def _load_runs() -> list[dict]:
    if not EVAL_RUNS_DIR.exists():
        return []
    runs = []
    for path in sorted(EVAL_RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                run = json.load(f)
            run["_path"] = str(path)
            runs.append(run)
        except Exception:
            continue
    return runs


runs = _load_runs()

st.markdown("""
<div class="eval-header">
  <div class="eval-brand">Case<span style="color:#7c3aed;">IQ</span>
    <span style="font-size:18px;font-weight:400;color:#94a3b8;margin-left:12px;">Evaluation Runs</span>
  </div>
  <div class="eval-subtitle">Automated Quality Suite · LangSmith Experiment View</div>
</div>
""", unsafe_allow_html=True)
st.divider()

if not runs:
    st.info("No local eval run reports found yet. Run `python3 run_evals.py` and add a report under `data/eval_runs/`.")
    st.stop()

run_options = {
    f"{r['experiment_name']} · {r.get('total_passed', 0)}/{r.get('total_tests', 0)} · {r.get('ran_at', '')}": r
    for r in runs
}
selected_label = st.selectbox("Eval Run", list(run_options.keys()), label_visibility="collapsed")
run = run_options[selected_label]

passed = int(run.get("total_passed", 0))
total = int(run.get("total_tests", 0))
failed = total - passed
pass_rate = float(run.get("pass_rate", 0))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pass Rate", f"{pass_rate:.0%}")
m2.metric("Passed", f"{passed}/{total}")
m3.metric("Failed", str(failed))
m4.metric("Eval Time", f"{float(run.get('elapsed_seconds', 0)):.1f}s")

st.caption(
    f"LangSmith: {run.get('project', 'support-intelligence-poc')} · "
    f"{run.get('dataset', 'support-intelligence-evals')} · "
    f"{run.get('experiment_name', '')}"
)

st.divider()

cat_df = pd.DataFrame(run.get("categories", []))
if not cat_df.empty:
    cat_df["Pass Rate"] = (cat_df["pass_rate"] * 100).round(0).astype(int).astype(str) + "%"
    cat_df = cat_df.rename(columns={"name": "Category", "passed": "Passed", "total": "Total"})
    st.subheader("Category Breakdown")
    st.dataframe(
        cat_df[["Category", "Passed", "Total", "Pass Rate"]],
        hide_index=True,
        use_container_width=True,
    )

result_df = pd.DataFrame(run.get("results", []))
if not result_df.empty:
    result_df["Status"] = result_df["passed"].map({True: "PASS", False: "FAIL"})
    result_df = result_df.rename(columns={"category": "Category", "label": "Test", "metric": "Metric"})
    st.subheader("Test Results")
    st.dataframe(
        result_df[["Status", "Category", "Test", "Metric"]],
        hide_index=True,
        use_container_width=True,
    )

    failing = result_df[result_df["Status"] == "FAIL"]
    if not failing.empty:
        st.subheader("Failures To Inspect")
        for _, row in failing.iterrows():
            st.markdown(f"- **{row['Category']}**: {row['Test']} `{row['Metric']}`")
