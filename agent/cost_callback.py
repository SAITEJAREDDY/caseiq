"""
LangSmith cost-tracking callback.
Rate: $1.00 per 1 000 tokens (demo). Attaches cost to every LLM run as
both extra metadata (visible in run detail) and a numeric feedback score
(visible in the Feedback tab).
"""
from langchain_core.callbacks import BaseCallbackHandler
from langsmith import Client as LangSmithClient

COST_PER_1K_TOKENS = 1.00  # $1.00 / 1 000 tokens — demo rate


class CostTrackingCallback(BaseCallbackHandler):
    _ls_client: LangSmithClient | None = None

    @classmethod
    def _client(cls) -> LangSmithClient:
        if cls._ls_client is None:
            cls._ls_client = LangSmithClient()
        return cls._ls_client

    def on_llm_end(self, response, *, run_id, **kwargs):
        usage      = (response.llm_output or {}).get("token_usage", {})
        total      = usage.get("total_tokens", 0)
        if not total:
            return

        prompt_tok = usage.get("prompt_tokens", 0)
        compl_tok  = usage.get("completion_tokens", 0)
        cost_usd   = round(total / 1_000 * COST_PER_1K_TOKENS, 4)

        try:
            ls = self._client()

            # Metadata visible in the run Extra / Metadata panel
            ls.update_run(
                run_id,
                extra={
                    "cost_usd":          cost_usd,
                    "prompt_tokens":     prompt_tok,
                    "completion_tokens": compl_tok,
                    "total_tokens":      total,
                    "rate_per_1k_usd":   COST_PER_1K_TOKENS,
                },
            )

            # Numeric feedback score visible in the Feedback tab
            ls.create_feedback(
                run_id=run_id,
                key="cost_usd",
                score=cost_usd,
                comment=(
                    f"${cost_usd:.4f}  "
                    f"({prompt_tok} prompt + {compl_tok} completion"
                    f" = {total} tokens @ ${COST_PER_1K_TOKENS:.2f}/1k)"
                ),
            )
        except Exception:
            pass  # never let telemetry crash the main flow
