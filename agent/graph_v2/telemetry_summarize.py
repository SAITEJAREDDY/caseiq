"""Deterministic case_telemetry.csv -> TelemetryFinding summarization.

Pure Python, no LLM, no randomness (spec section on not using an LLM during
graph loading). Groups raw metric samples into one finding per
(case_id, component_id, metric_code) -- the id is that composite key itself,
so re-running the loader is naturally idempotent with no synthetic id.

Normal (never-anomalous) findings are kept, not discarded: they eliminate
hypotheses just as usefully as an anomalous one confirms them.
"""
from collections import defaultdict

from agent.graph_v2.db import read_csv


def summarize(case_telemetry_path):
    groups = defaultdict(list)
    for row in read_csv(case_telemetry_path):
        key = (row["case_id"], row["component_id"], row["metric_code"])
        groups[key].append(row)

    findings = []
    for (case_id, component_id, metric_code), rows in groups.items():
        rows.sort(key=lambda r: r["timestamp"])
        values = [float(r["value"]) for r in rows]
        normal_values = [float(r["value"]) for r in rows if r["is_anomalous"] != "true"]
        anomalous_rows = [r for r in rows if r["is_anomalous"] == "true"]

        baseline = sum(normal_values) / len(normal_values) if normal_values else sum(values) / len(values)
        observed_min = min(values)
        observed_max = max(values)

        if anomalous_rows:
            status = "abnormal"
            anomaly_start = anomalous_rows[0]["timestamp"]
            anomaly_end = anomalous_rows[-1]["timestamp"]
            anomaly_peak = max(float(r["value"]) for r in anomalous_rows)
            direction = "above_baseline" if anomaly_peak >= baseline else "below_baseline"
        else:
            status = "normal"
            anomaly_start = None
            anomaly_end = None
            direction = None

        findings.append(
            {
                "id": f"{case_id}:{component_id}:{metric_code}",
                "case_id": case_id,
                "component_id": component_id,
                "metric_code": metric_code,
                "reading_count": len(rows),
                "window_start": rows[0]["timestamp"],
                "window_end": rows[-1]["timestamp"],
                "baseline": round(baseline, 4),
                "observed_min": round(observed_min, 4),
                "observed_max": round(observed_max, 4),
                "status": status,
                "direction": direction,
                "anomaly_start": anomaly_start,
                "anomaly_end": anomaly_end,
            }
        )
    return findings


if __name__ == "__main__":
    import sys

    from agent.graph_v2.config import DATA_PHASE2

    findings = summarize(DATA_PHASE2 / "case_telemetry.csv")
    print(f"{len(findings)} telemetry findings from case_telemetry.csv")
    abnormal = [f for f in findings if f["status"] == "abnormal"]
    print(f"  {len(abnormal)} abnormal, {len(findings) - len(abnormal)} normal")
    for f in findings[:3]:
        print(" ", f)
    for f in abnormal[:3]:
        print(" ", f)
