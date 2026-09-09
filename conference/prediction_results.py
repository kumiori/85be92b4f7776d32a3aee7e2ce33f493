from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class QuestionSignal:
    question_id: str
    field: str
    prompt: str
    context: str
    input_type: str
    n_participants: int
    n_answered: int
    n_skipped: int
    n_flagged: int
    denominator: int
    counts: tuple[tuple[str, int], ...] = ()
    excerpts: tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictionResults:
    participants: int
    submitted_questionnaires: int
    scientific_selections: int
    skipped_questions: int
    flagged_questions: int
    contributions_offered: int
    collaborative_challenges_selected: int
    questions: tuple[QuestionSignal, ...]


def _has_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value or "").strip())


def _values(value: Any) -> list[str]:
    source: Iterable[Any] = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(item).strip() for item in source if str(item or "").strip()]


def _is_skipped(submission: dict[str, Any], question_id: str) -> bool:
    states = submission.get("question_states")
    state = states.get(question_id, {}) if isinstance(states, dict) else {}
    if isinstance(state, dict) and str(state.get("answer_state") or "") == "skipped":
        return True
    skips = submission.get("question_skips")
    return isinstance(skips, dict) and question_id in skips


def _is_flagged(submission: dict[str, Any], question_id: str) -> bool:
    flags = submission.get("question_flags")
    payload = flags.get(question_id, {}) if isinstance(flags, dict) else {}
    if isinstance(payload, dict):
        return bool(payload.get("flags") or str(payload.get("note") or "").strip())
    return bool(payload)


def build_prediction_results(
    submissions: Sequence[dict[str, Any]], questions: Sequence[Any]
) -> PredictionResults:
    participant_keys = {
        str(item.get("player_id") or item.get("actor_key") or index)
        for index, item in enumerate(submissions)
    }
    question_signals: list[QuestionSignal] = []
    scientific_selections = 0
    skipped_questions = 0
    flagged_questions = 0

    for question in questions:
        question_id = str(question.question_id)
        field = str(question.field)
        option_labels = {
            str(option.get("value") or ""): str(option.get("label") or "")
            for option in question.options
        }
        raw_counts: Counter[str] = Counter()
        excerpts: list[str] = []
        n_answered = n_skipped = n_flagged = 0

        for submission in submissions:
            skipped = _is_skipped(submission, question_id)
            flagged = _is_flagged(submission, question_id)
            value = submission.get(field)
            if skipped:
                n_skipped += 1
            elif _has_value(value):
                n_answered += 1
                if str(question.input_type) == "text":
                    scientific_selections += 1
                    if len(excerpts) < 5:
                        excerpts.append(str(value).strip())
                else:
                    selected = _values(value)
                    scientific_selections += len(selected)
                    raw_counts.update(selected)
            if flagged:
                n_flagged += 1

        skipped_questions += n_skipped
        flagged_questions += n_flagged
        counts = tuple(
            (label, raw_counts.get(value, 0))
            for value, label in option_labels.items()
        )
        question_signals.append(
            QuestionSignal(
                question_id=question_id,
                field=field,
                prompt=str(question.prompt),
                context=str(getattr(question, "context", "") or ""),
                input_type=str(question.input_type),
                n_participants=len(participant_keys),
                n_answered=n_answered,
                n_skipped=n_skipped,
                n_flagged=n_flagged,
                denominator=n_answered,
                counts=counts,
                excerpts=tuple(excerpts),
            )
        )

    return PredictionResults(
        participants=len(participant_keys),
        submitted_questionnaires=len(submissions),
        scientific_selections=scientific_selections,
        skipped_questions=skipped_questions,
        flagged_questions=flagged_questions,
        contributions_offered=sum(
            1 for item in submissions if _has_value(item.get("contribution"))
        ),
        collaborative_challenges_selected=sum(
            1
            for item in submissions
            if not _is_skipped(item, "challenge") and _has_value(item.get("challenge"))
        ),
        questions=tuple(question_signals),
    )
