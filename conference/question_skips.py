from __future__ import annotations

from typing import Any, Dict, Iterable, List


QUESTION_SKIP_OPTIONS: List[Dict[str, str]] = [
    {"value": "not_relevant", "label": "Not relevant to me"},
    {"value": "dont_know", "label": "I don't know"},
    {"value": "prefer_not_to_answer", "label": "I prefer not to answer"},
    {
        "value": "dont_understand",
        "label": "I don't understand the question",
    },
    {"value": "no_option_fits", "label": "None of the options fit"},
    {
        "value": "too_difficult_briefly",
        "label": "Too difficult to answer briefly",
    },
    {"value": "other", "label": "Other"},
]

QUESTION_SKIP_LABELS = {
    str(item["value"]): str(item["label"]) for item in QUESTION_SKIP_OPTIONS
}

QUESTION_SKIP_INTRO = "You can skip this question. If you wish, tell us why."


def normalize_question_skips(raw: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}

    allowed = set(QUESTION_SKIP_LABELS)
    out: Dict[str, Dict[str, Any]] = {}
    for question_id, payload in raw.items():
        token = str(question_id or "").strip()
        if not token:
            continue
        reasons: Iterable[Any]
        note_source: Any = ""
        if isinstance(payload, dict):
            # `flags` is accepted only to read checkpoints produced before
            # Flag and Skip received separate metadata contracts.
            reasons = payload.get("reasons", payload.get("flags", []))
            note_source = payload.get("note", "")
            prior_legacy = payload.get("legacy_reasons", [])
        elif isinstance(payload, list):
            reasons = payload
            prior_legacy = []
        else:
            reasons = [payload]
            prior_legacy = []

        seen: set[str] = set()
        normalized_reasons: List[str] = []
        legacy_reasons: List[str] = [
            str(value).strip()
            for value in prior_legacy
            if str(value).strip()
        ]
        for value in reasons:
            reason = str(value or "").strip()
            if not reason or reason in seen:
                continue
            if reason in allowed:
                normalized_reasons.append(reason)
            elif reason not in legacy_reasons:
                legacy_reasons.append(reason)
            seen.add(reason)
        note = str(note_source or "").strip()[:500]
        if normalized_reasons or legacy_reasons or note:
            out[token] = {"reasons": normalized_reasons, "note": note}
            if legacy_reasons:
                out[token]["legacy_reasons"] = legacy_reasons
    return out
