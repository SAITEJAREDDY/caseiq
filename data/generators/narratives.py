"""
Turns deterministic ground-truth briefs (from generate_cases.py / the KB article
briefs in generate_structural.py) into natural-language text via Together AI
(Qwen/Qwen3.8-Flash). This is the only place in the Phase 1 pipeline that calls
an LLM.

Every case brief already carries a `difficulty_archetype` decided upstream,
deterministically, in Python. This module's job is narrow: render the
*observable* facts as customer-voice ticket text, following that archetype's
instruction for what to hide, blur, or get wrong — never leak the internal
`gt_*` taxonomy labels verbatim into the text a customer wouldn't actually say.
"""
import concurrent.futures as cf
import random
import time

from llm_client import chat_completion, parse_json_object, TogetherAuthError

CASE_BATCH_SIZE = 15
ARTICLE_BATCH_SIZE = 10
MAX_WORKERS = 10

ARCHETYPE_INSTRUCTIONS = {
    "clear": "Write a clear, reasonably well-organized ticket. The customer describes what "
             "they observed accurately and with enough detail to act on.",
    "vague": "Write a vague, underspecified ticket. Omit some details a support agent would "
             "actually need (e.g. no timestamps, no error codes, unclear scope). Keep it short.",
    "customer_misdiagnosis": "The customer confidently states their OWN theory of the cause "
             "(given below as customer_asserted_cause) as if it were fact, even though it is "
             "not the actual cause. Phrase it in plain customer language, e.g. \"We think it's "
             "because of X\" or \"This is definitely a Y problem\" — do not use technical taxonomy "
             "wording verbatim.",
    "wrong_product_mentioned": "The customer names the product given as 'product the customer "
             "believes is affected' (which may differ from the actual affected product) — write "
             "the ticket as if that's the product they think is broken.",
    "multi_component_symptoms": "The ticket should describe symptoms that could plausibly span "
             "both the primary affected area and the secondary area mentioned below, without the "
             "customer being able to tell which one is actually at fault.",
    "dependency_root_cause": "The customer believes the problem is in the product/component they "
             "are looking at, with no idea that the real cause may be an upstream/third-party "
             "dependency. Do not have the customer mention a vendor or dependency at all.",
}

_SYSTEM_PROMPT = """You are generating synthetic enterprise support ticket text for a dataset \
used to train and evaluate support-case classification systems. For each case in the input \
JSON array, write a realistic support ticket TITLE and DESCRIPTION as the customer would write \
it — not as an engineer would describe the internal diagnosis.

Vary sentence structure, technical sophistication, length, clarity, and tone across cases. Some \
customers are precise; some are rambling, use shorthand, misspell things, or bury the important \
detail in the third sentence. Never state the internal root cause, resolution type, issue \
subcategory, or team name verbatim — those are back-office labels the customer has never seen. \
Only reference the symptoms, environment, impact, and (if given) the customer's own \
theory/misdiagnosis.

Follow the "narrative_instruction" field for each case exactly.

Respond with ONLY a JSON object: {"cases": [{"i": <int>, "title": "...", "description": "..."}, ...]}\
 covering every case index in the input, in any order."""

_ARTICLE_SYSTEM_PROMPT = """You are writing internal knowledge-base articles for an enterprise \
support team, for a synthetic dataset used to build and evaluate KB-recommendation systems. For \
each article brief in the input JSON array, write a TITLE, a one-to-two sentence CONTENT_SUMMARY \
(what an agent sees in search results), and a CONTENT_BODY of 3-6 short sentences (a practical \
troubleshooting note: what to check, what usually causes it, how it's typically resolved) \
consistent with the given category/symptoms/root causes/resolutions. Vary style: some articles \
are broad and reference-like, some are narrowly specific with numbered steps. If "outdated" is \
true, the body should read like guidance that predates a later product change (e.g. reference an \
older flow) without literally saying "this article is outdated".

Respond with ONLY a JSON object: {"articles": [{"i": <int>, "title": "...", \
"content_summary": "...", "content_body": "..."}, ...]} covering every article index, in any order."""


def _case_payload(idx, brief):
    payload = {
        "i": idx,
        "product_customer_sees": brief["_product_reported_name"],
        "environment": brief["environment"],
        "region": brief["region"],
        "symptoms_observed": brief["_symptom_names"],
        "reported_business_impact": brief["reported_business_impact"],
        "reported_affected_users": brief["reported_affected_users"],
        "narrative_instruction": ARCHETYPE_INSTRUCTIONS[brief["difficulty_archetype"]],
    }
    if brief["difficulty_archetype"] == "customer_misdiagnosis":
        payload["customer_asserted_cause"] = brief["customer_asserted_cause"]
    if brief["difficulty_archetype"] == "multi_component_symptoms" and brief["_extra_component_name"]:
        payload["secondary_area_hint"] = brief["_extra_component_name"]
    return payload


def _article_payload(idx, brief):
    return {
        "i": idx,
        "category": brief["_category_name"] if "_category_name" in brief else None,
        "subcategory_names": brief.get("_subcategory_names", []),
        "symptom_names": brief.get("_symptom_names", []),
        "root_cause_names": brief.get("_root_cause_names", []),
        "resolution_names": brief.get("_resolution_names", []),
        "product_names": brief.get("_product_names", []),
        "specificity": brief["specificity"],
        "outdated": brief["outdated"],
    }


def _template_fallback_case(brief):
    symptoms = ", ".join(brief["_symptom_names"][:2]) or "an issue"
    brief["title"] = f"{brief['_product_reported_name']} — {symptoms}"
    brief["description"] = (
        f"We are seeing {symptoms} on {brief['_product_reported_name']} in {brief['environment']}. "
        f"Please advise."
    )


def _template_fallback_article(brief):
    brief["title"] = f"Troubleshooting {brief.get('_category_name', 'this issue')}"
    brief["content_summary"] = f"Guidance for resolving common issues in this area."
    brief["content_body"] = (
        "Review recent configuration changes, check for related alerts, and confirm the affected "
        "component's health before escalating."
    )


def _progress_line(label, done, total, start, width=30):
    elapsed = time.time() - start
    rate = done / elapsed if elapsed > 0 else 0
    eta_min = (total - done) / rate / 60 if rate > 0 else 0
    pct = done / total * 100
    filled = int(pct / 100 * width)
    bar = "#" * filled + "-" * (width - filled)
    return (f"  {label}: [{bar}] {pct:5.1f}%  {done:>5}/{total}  "
            f"elapsed {elapsed / 60:5.1f}m  ETA {eta_min:5.1f}m")


def _run_batches(batches, worker_fn, fallback_single_fn, fallback_template_fn, label):
    total = len(batches)
    done = 0
    start = time.time()
    step = 20  # print a progress line every 20 completed batches
    print(_progress_line(label, 0, total, start), flush=True)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(worker_fn, batch): batch for batch in batches}
        for fut in cf.as_completed(futures):
            batch = futures[fut]
            done += 1
            try:
                fut.result()
            except TogetherAuthError:
                raise
            except Exception as e:
                print(f"  {label}: batch failed ({type(e).__name__}: {e}); falling back per-case", flush=True)
                for item in batch:
                    try:
                        fallback_single_fn(item)
                    except Exception as e2:
                        print(f"  {label}: single fallback also failed ({type(e2).__name__}: {e2}); using template",
                              flush=True)
                        fallback_template_fn(item)
            if done % step == 0 or done == total:
                print(_progress_line(label, done, total, start), flush=True)


def fill_case_narratives(briefs, seed=42):
    def worker(batch):
        payload = [_case_payload(idx, b) for idx, b in batch]
        messages = [{"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": str(payload)}]
        text = chat_completion(messages, temperature=0.9, max_tokens=2600, seed=seed)
        data = parse_json_object(text)
        by_idx = {c["i"]: c for c in data["cases"]}
        for idx, b in batch:
            if idx in by_idx:
                b["title"] = by_idx[idx]["title"]
                b["description"] = by_idx[idx]["description"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, b = item
        payload = [_case_payload(0, b)]
        messages = [{"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": str(payload)}]
        text = chat_completion(messages, temperature=0.9, max_tokens=500, seed=seed)
        data = parse_json_object(text)
        c = data["cases"][0]
        b["title"], b["description"] = c["title"], c["description"]

    def fallback_template(item):
        _idx, b = item
        _template_fallback_case(b)

    indexed = list(enumerate(briefs))
    batches = [indexed[i:i + CASE_BATCH_SIZE] for i in range(0, len(indexed), CASE_BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "case narratives")


def fill_article_narratives(briefs, name_lookup, seed=42):
    """name_lookup resolves the id lists stashed on each brief (_category_id etc.) to
    human-readable names, since generate_structural.py stores ids to keep the brief compact."""
    for b in briefs:
        b["_category_name"] = name_lookup["category"].get(b["_category_id"], "")
        b["_subcategory_names"] = [name_lookup["subcategory"].get(i, "") for i in b["_subcategory_ids"]]
        b["_symptom_names"] = [name_lookup["symptom"].get(i, "") for i in b["_symptom_ids"]]
        b["_root_cause_names"] = [name_lookup["root_cause"].get(i, "") for i in b["_root_cause_ids"]]
        b["_resolution_names"] = [name_lookup["resolution"].get(i, "") for i in b["_resolution_ids"]]
        b["_product_names"] = [name_lookup["product"].get(i, "") for i in b["_product_ids"]]

    def worker(batch):
        payload = [_article_payload(idx, b) for idx, b in batch]
        messages = [{"role": "system", "content": _ARTICLE_SYSTEM_PROMPT},
                    {"role": "user", "content": str(payload)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=2600, seed=seed)
        data = parse_json_object(text)
        by_idx = {a["i"]: a for a in data["articles"]}
        for idx, b in batch:
            if idx in by_idx:
                b["title"] = by_idx[idx]["title"]
                b["content_summary"] = by_idx[idx]["content_summary"]
                b["content_body"] = by_idx[idx]["content_body"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, b = item
        payload = [_article_payload(0, b)]
        messages = [{"role": "system", "content": _ARTICLE_SYSTEM_PROMPT},
                    {"role": "user", "content": str(payload)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=600, seed=seed)
        data = parse_json_object(text)
        a = data["articles"][0]
        b["title"], b["content_summary"], b["content_body"] = a["title"], a["content_summary"], a["content_body"]

    def fallback_template(item):
        _idx, b = item
        _template_fallback_article(b)

    indexed = list(enumerate(briefs))
    batches = [indexed[i:i + ARTICLE_BATCH_SIZE] for i in range(0, len(indexed), ARTICLE_BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "KB narratives")
