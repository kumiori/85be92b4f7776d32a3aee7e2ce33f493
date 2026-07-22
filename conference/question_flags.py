from __future__ import annotations

from typing import Any, Dict, Iterable, List


QUESTION_FLAG_OPTIONS: List[Dict[str, str]] = [
    {"value": "interesting_question", "label": "Interesting question"},
    {"value": "useful_for_coordination", "label": "Useful for coordination"},
    {"value": "incomplete", "label": "Incomplete"},
    {"value": "misleading", "label": "Misleading"},
    {"value": "too_narrow", "label": "Too narrow"},
    {"value": "unclear", "label": "Unclear"},
    {"value": "missing_option", "label": "Missing option"},
]

QUESTION_FLAG_LABELS = {
    str(item["value"]): str(item["label"]) for item in QUESTION_FLAG_OPTIONS
}


def question_flag_values() -> set[str]:
    return set(QUESTION_FLAG_LABELS)


def normalize_question_flags(raw: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}

    allowed = question_flag_values()
    out: Dict[str, Dict[str, Any]] = {}
    for question_id, payload in raw.items():
        token = str(question_id or "").strip()
        if not token:
            continue

        flags: Iterable[Any]
        note_source: Any = ""
        if isinstance(payload, dict):
            flags = payload.get("flags", [])
            note_source = payload.get("note", "")
        elif isinstance(payload, list):
            flags = payload
        else:
            flags = [payload]

        seen: set[str] = set()
        normalized_flags: List[str] = []
        for value in flags:
            flag = str(value or "").strip()
            if not flag or flag not in allowed or flag in seen:
                continue
            normalized_flags.append(flag)
            seen.add(flag)

        note = str(note_source or "").strip()[:500]
        if normalized_flags or note:
            out[token] = {"flags": normalized_flags, "note": note}
    return out
