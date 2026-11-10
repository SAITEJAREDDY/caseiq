"""The one authoritative final-answer contract (Phase 9A sections 16-21, 24).

The model writes registry aliases; this module validates them, maps them back to canonical ids deterministically, and reshapes the
result into the Phase 5 persisted `final_diagnosis` shape so the unchanged Phase 6 evaluator can score it. Nothing is repaired here: a
final answer that fails validation is rejected with structured errors (one correction attempt is allowed by the loop, then
CONTRACT_FAILURE).

Statuses
  DIAGNOSIS_PROPOSED      >=1 supported hypothesis, valid citations, non-null confidence; sufficiency may not be "insufficient".
  INSUFFICIENT_EVIDENCE   every diagnostic field may be null; sufficiency must not be "sufficient".
  HUMAN_REVIEW_REQUIRED   human_review_required must be true, with a reason.
  CONTRACT_FAILURE        assigned only by the harness (never model-selectable); no diagnosis is pretended.
A null selection is always valid: abstaining is better than an invented id.
"""
from agent.agent_v3.catalog import _enum, alias_or_null, citation_array, err, hypothesis_schema, nullable, parse_json, validate_citations, validate_hypotheses
from agent.agent_v3.config import LINE_MAX, SUMMARY_MAX
from agent.agent_v3.registry import ALIAS_RE, CITABLE_KINDS, ID_RE, ObservedEntityRegistry

MODEL_STATUSES = ("DIAGNOSIS_PROPOSED", "INSUFFICIENT_EVIDENCE", "HUMAN_REVIEW_REQUIRED")
ALL_STATUSES = MODEL_STATUSES + ("CONTRACT_FAILURE",)
SUFFICIENCY = ("sufficient", "partial", "insufficient")
# (value field, its confidence field, allowed alias kinds)
SELECTIONS = (
    ("issue_category", "category_confidence", ("CATEGORY",)),
    ("root_cause", "root_cause_confidence", ("CAUSE",)),
    ("affected_component", "component_confidence", ("COMPONENT",)),
    ("causal_change", "causal_change_confidence", ("CHANGE",)),
    ("owning_team", "routing_confidence", ("TEAM",)),
)
FINAL_FIELDS = ("hypotheses", "evidence_ids") + tuple(f for s in SELECTIONS for f in s[:2]) + (
    "confidence", "evidence_sufficiency", "human_review_required", "review_reason", "status", "recommended_next_action",
    "unresolved_uncertainties", "summary")
_CONF = {"type": "number", "minimum": 0, "maximum": 1}


def final_schema(registry: ObservedEntityRegistry) -> dict:
    props = {"hypotheses": hypothesis_schema(registry), "evidence_ids": citation_array(registry.aliases(*CITABLE_KINDS))}
    for value, conf, kinds in SELECTIONS:
        props[value] = alias_or_null(registry.aliases(*kinds))
        props[conf] = nullable(_CONF)
    props.update({
        "confidence": _CONF,
        "evidence_sufficiency": _enum(SUFFICIENCY),
        "human_review_required": {"type": "boolean"},
        "review_reason": nullable({"type": "string", "maxLength": LINE_MAX}),
        "status": _enum(MODEL_STATUSES),
        "recommended_next_action": {"type": "string", "maxLength": LINE_MAX},
        "unresolved_uncertainties": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": LINE_MAX}},
        "summary": {"type": "string", "maxLength": SUMMARY_MAX},
    })
    return {"type": "object", "additionalProperties": False, "required": list(FINAL_FIELDS), "properties": props}


def _text_errors(text, field, registry) -> list:
    """Free text may mention aliases (they must be real) but never an internal id."""
    errors = []
    if not isinstance(text, str):
        return [err("bad_type", field, "expected text")]
    if ID_RE.search(text):
        errors.append(err("canonical_id_used", field, "an internal id appears in text"))
    for m in ALIAS_RE.finditer(text):
        if registry.get(m.group(0)) is None:
            errors.append(err("unknown_alias", field, f"{m.group(0)!r} is not in the registry"))
    return errors


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def supported_hypotheses(final: dict) -> list:
    """A hypothesis is supported when it is not rejected and cites at least one item as support."""
    return [h for h in final.get("hypotheses") or [] if h.get("status") != "rejected" and h.get("supporting_evidence")]


def validate_final(raw, registry: ObservedEntityRegistry) -> tuple:
    """(final|None, errors). Structural, alias, evidence, nullability, confidence-bound and status-requirement checks, all deterministic."""
    obj, e = parse_json(raw)
    if e:
        return None, [e]
    errors = []
    for k in FINAL_FIELDS:
        if k not in obj:
            errors.append(err("missing_field", k))
    for k in sorted(set(obj) - set(FINAL_FIELDS)):
        errors.append(err("unknown_field", k, "not part of the final schema"))
    if errors and any(x["code"] == "missing_field" for x in errors):
        # a structurally incomplete object cannot be checked further without guessing
        return None, errors

    errors += validate_hypotheses(obj["hypotheses"], registry)
    errors += validate_citations(obj["evidence_ids"], registry, "evidence_ids")
    cited = set(obj["evidence_ids"]) if isinstance(obj["evidence_ids"], list) else set()

    any_selection = False
    for value, conf, kinds in SELECTIONS:
        v, c = obj[value], obj[conf]
        if v is None:
            if c is not None:
                errors.append(err("confidence_without_selection", conf, f"{conf} must be null when {value} is null"))
            continue
        any_selection = True
        if not isinstance(v, str):
            errors.append(err("bad_type", value, "expected an alias or null"))
        elif ID_RE.search(v):
            errors.append(err("canonical_id_used", value, "an internal id was written instead of an alias"))
        elif registry.get(v) is None:
            errors.append(err("unknown_alias", value, f"{v!r} is not in the registry"))
        elif registry.get(v).kind not in kinds:
            errors.append(err("alias_wrong_kind", value, f"{v!r} is a {registry.get(v).kind} alias; expected {'/'.join(kinds)}"))
        if c is None or not _is_number(c) or not 0 <= c <= 1:
            errors.append(err("confidence_required", conf, f"{value} is set, so {conf} must be a number between 0 and 1"))
    if any_selection and not obj["evidence_ids"]:
        errors.append(err("selection_without_citation", "evidence_ids", "a diagnostic selection needs at least one cited evidence item"))
    if obj["causal_change"] is not None and isinstance(obj["causal_change"], str) and obj["causal_change"] not in cited:
        errors.append(err("causal_change_not_cited", "evidence_ids", "the selected causal_change must also be cited in evidence_ids"))
    if isinstance(obj["hypotheses"], list):
        for i, h in enumerate(obj["hypotheses"]):
            if isinstance(h, dict):
                for k in ("supporting_evidence", "contradicting_evidence"):
                    for a in h.get(k) or []:
                        if isinstance(a, str) and a not in cited:
                            errors.append(err("hypothesis_citation_not_in_evidence_ids", f"hypotheses[{i}].{k}", f"{a!r} must also be listed in evidence_ids"))

    if not _is_number(obj["confidence"]) or not 0 <= obj["confidence"] <= 1:
        errors.append(err("confidence_range", "confidence", "a number between 0 and 1"))
    if obj["status"] not in MODEL_STATUSES:
        errors.append(err("bad_enum", "status", f"one of {list(MODEL_STATUSES)}"))
    if obj["evidence_sufficiency"] not in SUFFICIENCY:
        errors.append(err("bad_enum", "evidence_sufficiency", f"one of {list(SUFFICIENCY)}"))
    if not isinstance(obj["human_review_required"], bool):
        errors.append(err("bad_type", "human_review_required", "expected true or false"))
    if obj["review_reason"] is not None:
        errors += _text_errors(obj["review_reason"], "review_reason", registry)
    for k, mx in (("recommended_next_action", LINE_MAX), ("summary", SUMMARY_MAX)):
        if not isinstance(obj[k], str) or not obj[k].strip():
            errors.append(err("bad_value", k, "non-empty text"))
        else:
            errors += _text_errors(obj[k], k, registry)
            if len(obj[k]) > mx:
                errors.append(err("bad_value", k, f"at most {mx} characters"))
    if not isinstance(obj["unresolved_uncertainties"], list) or not all(isinstance(x, str) for x in obj["unresolved_uncertainties"]):
        errors.append(err("bad_type", "unresolved_uncertainties", "expected a list of text"))
    else:
        for x in obj["unresolved_uncertainties"]:
            errors += _text_errors(x, "unresolved_uncertainties", registry)
    if isinstance(obj["hypotheses"], list):
        for h in obj["hypotheses"]:
            if isinstance(h, dict) and isinstance(h.get("label"), str):
                errors += _text_errors(h["label"], "hypotheses.label", registry)

    status = obj["status"]
    if status == "DIAGNOSIS_PROPOSED":
        if not supported_hypotheses(obj):
            errors.append(err("proposed_without_supported_hypothesis", "status", "DIAGNOSIS_PROPOSED needs a non-rejected hypothesis with cited support"))
        if obj["evidence_sufficiency"] == "insufficient":
            errors.append(err("status_sufficiency_conflict", "evidence_sufficiency", "a diagnosis cannot be proposed while claiming insufficient evidence"))
    elif status == "INSUFFICIENT_EVIDENCE":
        if obj["evidence_sufficiency"] == "sufficient":
            errors.append(err("status_sufficiency_conflict", "evidence_sufficiency", "INSUFFICIENT_EVIDENCE cannot claim sufficient evidence"))
    elif status == "HUMAN_REVIEW_REQUIRED":
        if obj["human_review_required"] is not True:
            errors.append(err("review_flag_missing", "human_review_required", "HUMAN_REVIEW_REQUIRED needs human_review_required = true"))
        if not (isinstance(obj["review_reason"], str) and obj["review_reason"].strip()):
            errors.append(err("review_reason_missing", "review_reason", "HUMAN_REVIEW_REQUIRED needs a reason"))
    return (None if errors else obj), errors


# ── canonical mapping and the fallback ───────────────────────────────────────

def to_phase5_final(final: dict, registry: ObservedEntityRegistry) -> dict:
    """Validated alias-form final -> the Phase 5 `final_diagnosis` shape, with canonical ids (the deterministic alias -> id map)."""
    canon = lambda a: registry.canonical(a) if a else None
    conf = lambda k: final.get(k)
    root_cause_name = registry.get(final["root_cause"]).display_name if final.get("root_cause") else None
    hyps = [{"label": h["label"], "description": "", "confidence": h["confidence"], "status": h["status"],
             "supporting_evidence": [canon(a) for a in h["supporting_evidence"]],
             "contradicting_evidence": [canon(a) for a in h["contradicting_evidence"]]} for h in final["hypotheses"]]
    return {
        "hypotheses": hyps, "rationale": "",
        "predicted_product_id": None, "product_confidence": None,
        "predicted_component_id": canon(final["affected_component"]), "component_confidence": conf("component_confidence"),
        "predicted_category_id": canon(final["issue_category"]), "category_confidence": conf("category_confidence"),
        "predicted_subcategory_id": None,
        "predicted_root_cause_family": root_cause_name, "root_cause_confidence": conf("root_cause_confidence"),
        "predicted_causal_change_id": canon(final["causal_change"]), "causal_change_confidence": conf("causal_change_confidence"),
        "predicted_severity": None, "severity_confidence": None,
        "recommended_team_id": canon(final["owning_team"]), "routing_confidence": conf("routing_confidence"),
        "evidence_sufficiency": final["evidence_sufficiency"], "overall_confidence": final["confidence"],
        "recommended_next_action": final["recommended_next_action"], "human_review_required": final["human_review_required"],
        "human_review_reason": final["review_reason"], "evidence_summary": final["summary"],
        "unresolved_uncertainties": list(final["unresolved_uncertainties"]),
        "status": final["status"], "evidence_ids": [canon(a) for a in final["evidence_ids"]],
    }


def contract_failure_final(reason: str) -> dict:
    """No diagnosis is pretended. Same shape as a normal final so downstream code needs no special case."""
    return {
        "hypotheses": [], "rationale": "", "predicted_product_id": None, "product_confidence": None,
        "predicted_component_id": None, "component_confidence": None, "predicted_category_id": None, "category_confidence": None,
        "predicted_subcategory_id": None, "predicted_root_cause_family": None, "root_cause_confidence": None,
        "predicted_causal_change_id": None, "causal_change_confidence": None, "predicted_severity": None, "severity_confidence": None,
        "recommended_team_id": None, "routing_confidence": None, "evidence_sufficiency": "insufficient", "overall_confidence": 0.0,
        "recommended_next_action": "route to a human investigator", "human_review_required": True, "human_review_reason": reason,
        "evidence_summary": "The run ended in a contract failure; no diagnosis was produced.", "unresolved_uncertainties": [reason],
        "status": "CONTRACT_FAILURE", "evidence_ids": [],
    }
