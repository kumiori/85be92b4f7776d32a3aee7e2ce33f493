from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


ANSWER_STATES = {"unanswered", "answered", "skipped"}


def question_state(states: Mapping[str, Any] | None, question_id: str) -> dict[str, Any]:
    value = (states or {}).get(str(question_id or ""), {})
    if not isinstance(value, Mapping):
        value = {}
    answer_state = str(value.get("answer_state") or "unanswered")
    if answer_state not in ANSWER_STATES:
        answer_state = "unanswered"
    return {
        "answer_state": answer_state,
        "flagged": bool(value.get("flagged")),
    }


def _update(
    states: Mapping[str, Any] | None,
    question_id: str,
    *,
    answer_state: str | None = None,
    flagged: bool | None = None,
) -> dict[str, Any]:
    out = deepcopy(dict(states or {}))
    token = str(question_id or "").strip()
    if not token:
        return out
    current = question_state(out, token)
    if answer_state is not None:
        if answer_state not in ANSWER_STATES:
            raise ValueError(f"Unknown question answer state: {answer_state}")
        current["answer_state"] = answer_state
    if flagged is not None:
        current["flagged"] = bool(flagged)
    out[token] = current
    return out


def answer_question(states: Mapping[str, Any] | None, question_id: str) -> dict[str, Any]:
    return _update(states, question_id, answer_state="answered")


def skip_question(states: Mapping[str, Any] | None, question_id: str) -> dict[str, Any]:
    return _update(states, question_id, answer_state="skipped")


def flag_question(
    states: Mapping[str, Any] | None, question_id: str, *, flagged: bool
) -> dict[str, Any]:
    return _update(states, question_id, flagged=flagged)
