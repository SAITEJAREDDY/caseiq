"""
LangSmith Experiments logger for CaseIQ evaluation suite.

How LangSmith experiments work in 0.1.x
─────────────────────────────────────────
  Dataset  ─── contains Examples (one per test case)
     └── Experiment project  ─── created with reference_dataset_id=dataset.id
               └── Runs  ─── one per test case, reference_example_id=example.id
                    └── Feedback  ─── pass/fail + numeric score

Creating a project WITH reference_dataset_id is what makes it appear in
LangSmith's Experiments tab.  Plain create_run() goes to Traces only.
"""
from __future__ import annotations

import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.settings as cfg  # sets LANGCHAIN_* env vars

DATASET_NAME   = "support-intelligence-evals"
BASE_PROJECT   = cfg.LANGCHAIN_PROJECT   # "support-intelligence-poc"


class EvalLogger:
    """
    Wraps LangSmith client to log eval runs as a proper Experiment
    (visible under Datasets & Testing → <dataset> → Experiments tab).
    Non-blocking: any LangSmith failure degrades silently.
    """

    def __init__(self) -> None:
        self._ok              = False
        self._client          = None
        self._dataset_id: str | None  = None
        self._exp_project: str | None = None   # the per-run experiment project name
        self._run_count       = 0
        self.experiment_name: str | None = None

        try:
            from langsmith import Client
            self._client = Client()
            self._ok     = True
        except Exception as exc:
            print(f"[LangSmith] Client init failed — logging disabled. ({exc})")

    # ── Public API ─────────────────────────────────────────────────────────────

    def initialize_experiment(self, base_name: str = "evals-support-intelligence") -> str:
        """
        1. Create/reuse the shared dataset.
        2. Create a NEW project for this run linked to the dataset via
           reference_dataset_id — that's what makes it appear in Experiments.
        Returns the experiment name.
        """
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.experiment_name = f"{base_name}-{ts}"
        self._exp_project    = self.experiment_name   # project name = experiment name

        if not self._ok:
            return self.experiment_name

        # ── Step 1: ensure shared dataset exists ──────────────────────────────
        try:
            try:
                ds = self._client.read_dataset(dataset_name=DATASET_NAME)
            except Exception:
                ds = self._client.create_dataset(
                    dataset_name=DATASET_NAME,
                    description=(
                        "CaseIQ automated evaluation suite — "
                        "skill matching · confidence calibration · semantic search · "
                        "graceful degradation · latency · resolution time"
                    ),
                )
            self._dataset_id = str(ds.id)
        except Exception as exc:
            print(f"[LangSmith] Dataset setup failed: {exc}")
            return self.experiment_name

        # ── Step 2: create experiment project linked to the dataset ───────────
        try:
            self._client.create_project(
                project_name=self._exp_project,
                description=f"CaseIQ eval run {ts}",
                reference_dataset_id=self._dataset_id,
                upsert=True,
            )
            print(f"[LangSmith] Experiment : {self.experiment_name}")
            print(f"[LangSmith] Dataset    : {DATASET_NAME}  (id={self._dataset_id[:8]}…)")
            print(f"[LangSmith] View at    : smith.langchain.com → Datasets & Testing → {DATASET_NAME}")
        except Exception as exc:
            print(f"[LangSmith] Could not create experiment project: {exc}")

        return self.experiment_name

    def log_eval_result(
        self,
        eval_category: str,
        test_input: dict,
        output: Any,
        passed: bool,
        score_or_metric: float | int | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        For one test case:
          1. Create an Example in the dataset (represents the test input).
          2. Create a Run in the experiment project referencing that example.
          3. Attach pass/fail and numeric score as Feedback on the run.
        """
        if not self._ok or not self._exp_project or not self._dataset_id:
            return

        run_id = str(uuid.uuid4())
        now    = datetime.now(tz=timezone.utc)
        all_tags = [self.experiment_name, eval_category] + (tags or [])

        try:
            # ── 1. Create example in the shared dataset ────────────────────────
            example_id = None
            try:
                ex = self._client.create_example(
                    inputs=test_input,
                    outputs={"expected_passed": True},   # ground truth: all evals should pass
                    metadata={
                        "eval_category": eval_category,
                        "experiment":    self.experiment_name,
                    },
                    dataset_id=self._dataset_id,
                )
                example_id = str(ex.id)
            except Exception as ex_err:
                pass   # missing example doesn't block the run

            # ── 2. Create run in the experiment project ────────────────────────
            self._client.create_run(
                id=run_id,
                name=eval_category,
                run_type="chain",
                inputs=test_input,
                start_time=now,
                end_time=now,
                outputs={
                    "result": output if not isinstance(output, dict) else None,
                    **({} if not isinstance(output, dict) else output),
                    "passed": passed,
                },
                project_name=self._exp_project,   # ← experiment project, not base project
                tags=all_tags,
                extra={
                    "metadata": {
                        **(metadata or {}),
                        "passed":     passed,
                        "experiment": self.experiment_name,
                    }
                },
                **({"reference_example_id": example_id} if example_id else {}),
            )

            # ── 3. Feedback ────────────────────────────────────────────────────
            self._client.create_feedback(
                run_id=run_id,
                key="pass",
                score=1.0 if passed else 0.0,
                value="pass" if passed else "fail",
                source_info={"experiment": self.experiment_name},
            )
            if score_or_metric is not None:
                try:
                    self._client.create_feedback(
                        run_id=run_id,
                        key="score",
                        score=round(float(score_or_metric), 4),
                        source_info={"experiment": self.experiment_name},
                    )
                except Exception:
                    pass

            self._run_count += 1

        except Exception as exc:
            print(f"  [LangSmith] ⚠  Failed to log {eval_category}: {exc}")

    def finalize_experiment(
        self,
        total_passed: int,
        total_tests: int,
        pass_rate: float,
    ) -> None:
        """Log a summary run and print the exact LangSmith URL to visit."""
        if not self._ok or not self._exp_project:
            return

        run_id = str(uuid.uuid4())
        now    = datetime.now(tz=timezone.utc)

        try:
            self._client.create_run(
                id=run_id,
                name="experiment_summary",
                run_type="chain",
                inputs={"experiment": self.experiment_name, "total_tests": total_tests},
                start_time=now,
                end_time=now,
                outputs={
                    "total_passed":  total_passed,
                    "total_failed":  total_tests - total_passed,
                    "pass_rate":     round(pass_rate, 4),
                    "pass_rate_pct": f"{pass_rate * 100:.1f}%",
                    "logged_runs":   self._run_count,
                },
                project_name=self._exp_project,
                tags=[self.experiment_name, "summary"],
            )
            self._client.create_feedback(
                run_id=run_id,
                key="overall_pass_rate",
                score=round(pass_rate, 4),
                source_info={"experiment": self.experiment_name},
            )
        except Exception as exc:
            print(f"[LangSmith] Failed to log summary run: {exc}")

        print(
            f"\n[LangSmith] {self._run_count} runs logged.\n"
            f"  → smith.langchain.com\n"
            f"    Datasets & Testing → {DATASET_NAME} → Experiments tab\n"
            f"    Experiment name: {self.experiment_name}"
        )

    @property
    def ready(self) -> bool:
        return self._ok


# ── Module-level singleton ─────────────────────────────────────────────────────
eval_logger = EvalLogger()
