from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from conference.events import (
    COMPLEXITY_SESSION_CODE,
    COMPLEXITY_TEXT_ID,
    DALAMBERTIENNES_SESSION_CODE,
    DALAMBERTIENNES_TEXT_ID,
    UN_WG2_SESSION_CODE,
    UN_WG2_TEXT_ID,
    YOUNG_SESSION_CODE,
    YOUNG_TEXT_ID,
    conference_event_context,
    event_config_for_session_code,
)
from conference.question_sets import (
    QuestionSet,
    event_specific_question_ids,
    question_ids,
    shared_question_ids,
    validate_question_set,
)
from conference.question_sets.complexity_v2 import (
    QUESTION_SET as COMPLEXITY_V2_QUESTION_SET,
)
from conference.question_sets.dalembertiennes_v1 import (
    QUESTION_SET as DALEMBERTIENNES_V1_QUESTION_SET,
)
from conference.question_sets.pisa_session_v2 import (
    QUESTION_SET as PISA_SESSION_V2_QUESTION_SET,
)
from conference.question_sets.un_wg2_v1 import QUESTION_SET as UN_WG2_V1_QUESTION_SET


@dataclass(frozen=True)
class QuestionSetRegistryEntry:
    event_slug: str
    session_code: str
    text_ids: tuple[str, ...]
    question_set_id: str
    schema_id: str
    question_set: QuestionSet


@dataclass(frozen=True)
class ResolvedQuestionSetBundle:
    event_slug: str
    session_code: str
    text_id: str
    question_set_id: str
    schema_id: str
    question_set_module: str
    question_set_source_kind: str
    question_set_source_path: str
    question_set_source_note: str
    question_ids: tuple[str, ...]
    shared_question_ids: tuple[str, ...]
    event_specific_question_ids: tuple[str, ...]
    question_set: QuestionSet


_REGISTRY: tuple[QuestionSetRegistryEntry, ...] = (
    QuestionSetRegistryEntry(
        event_slug="complexity",
        session_code=COMPLEXITY_SESSION_CODE,
        text_ids=(COMPLEXITY_TEXT_ID, "complexity_session_v2"),
        question_set_id="complexity_v2",
        schema_id="complexity_v2",
        question_set=COMPLEXITY_V2_QUESTION_SET,
    ),
    QuestionSetRegistryEntry(
        event_slug="dalembertiennes",
        session_code=DALAMBERTIENNES_SESSION_CODE,
        text_ids=(DALAMBERTIENNES_TEXT_ID, "dalembertiennes_v0"),
        question_set_id="dalembertiennes_v1",
        schema_id="dalembertiennes_v1",
        question_set=DALEMBERTIENNES_V1_QUESTION_SET,
    ),
    QuestionSetRegistryEntry(
        event_slug="young",
        session_code=YOUNG_SESSION_CODE,
        text_ids=(YOUNG_TEXT_ID,),
        question_set_id="pisa_session_v2",
        schema_id="pisa_session_v2",
        question_set=PISA_SESSION_V2_QUESTION_SET,
    ),
    QuestionSetRegistryEntry(
        event_slug="un_wg2_visibility",
        session_code=UN_WG2_SESSION_CODE,
        text_ids=(UN_WG2_TEXT_ID,),
        question_set_id="un_wg2_v1",
        schema_id="questionnaire_v1",
        question_set=UN_WG2_V1_QUESTION_SET,
    ),
)


def _canonical_session_code(value: Any) -> str:
    return str(value or "").strip()


def registered_question_sets() -> tuple[QuestionSetRegistryEntry, ...]:
    return _REGISTRY


def conference_question_ids() -> set[str]:
    out: set[str] = set()
    for entry in _REGISTRY:
        out.update(question_ids(entry.question_set))
    return out


def resolve_question_set_bundle(
    *,
    session: Dict[str, Any] | None = None,
    session_code: str = "",
    text_id: str = "",
) -> ResolvedQuestionSetBundle:
    resolved_session_code = _canonical_session_code(
        session_code or (session or {}).get("session_code") or ""
    )
    resolved_text_id = _canonical_session_code(text_id)
    if not resolved_text_id and session:
        context = conference_event_context(session=session)
        resolved_text_id = _canonical_session_code(context.get("text_id"))

    entry = None
    if resolved_session_code:
        entry = next(
            (
                item
                for item in _REGISTRY
                if _canonical_session_code(item.session_code) == resolved_session_code
            ),
            None,
        )
    if entry is None and resolved_text_id:
        entry = next(
            (item for item in _REGISTRY if resolved_text_id in item.text_ids),
            None,
        )
    if entry is None:
        raise ValueError(
            f"No registered conference question set for session_code={resolved_session_code!r} text_id={resolved_text_id!r}"
        )

    context = conference_event_context(session=session, session_code=entry.session_code)
    config = event_config_for_session_code(entry.session_code)
    canonical_text_id = (
        resolved_text_id
        or (_canonical_session_code(context.get("text_id")) if config else "")
        or entry.text_ids[0]
    )
    return ResolvedQuestionSetBundle(
        event_slug=str(
            (context.get("event_slug") if config else "") or entry.event_slug
        ),
        session_code=str(
            (context.get("session_code") if config else "") or entry.session_code
        ),
        text_id=canonical_text_id,
        question_set_id=entry.question_set_id,
        schema_id=entry.schema_id,
        question_set_module=entry.question_set.source_module,
        question_set_source_kind=str(
            getattr(entry.question_set, "source_kind", "") or "python"
        ),
        question_set_source_path=str(
            getattr(entry.question_set, "source_path", "") or ""
        ),
        question_set_source_note=str(
            getattr(entry.question_set, "source_note", "") or ""
        ),
        question_ids=tuple(question_ids(entry.question_set)),
        shared_question_ids=tuple(shared_question_ids(entry.question_set)),
        event_specific_question_ids=tuple(
            event_specific_question_ids(entry.question_set)
        ),
        question_set=entry.question_set,
    )


def registry_validation_errors() -> list[str]:
    errors: List[str] = []
    seen_ids: set[str] = set()
    for entry in _REGISTRY:
        if entry.question_set_id in seen_ids:
            errors.append(
                f"Duplicate registered question_set_id: {entry.question_set_id}"
            )
        seen_ids.add(entry.question_set_id)
        errors.extend(validate_question_set(entry.question_set))
    return errors


def bundle_inspector_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _REGISTRY:
        session = {
            "session_code": entry.session_code,
            "session_title": entry.event_slug,
            "session_name": entry.event_slug,
        }
        context = conference_event_context(
            session=session, session_code=entry.session_code
        )
        config = event_config_for_session_code(entry.session_code)
        rows.append(
            {
                "event_slug": str(
                    (context.get("event_slug") if config else "") or entry.event_slug
                ),
                "session_code": entry.session_code,
                "text_id": (context.get("text_id") if config else "")
                or entry.text_ids[0],
                "question_set_id": entry.question_set_id,
                "schema_id": entry.schema_id,
                "question_set_module": entry.question_set.source_module,
                "question_set_source_kind": str(
                    getattr(entry.question_set, "source_kind", "") or "python"
                ),
                "question_set_source_path": str(
                    getattr(entry.question_set, "source_path", "") or ""
                ),
                "question_set_source_note": str(
                    getattr(entry.question_set, "source_note", "") or ""
                ),
                "question_count": len(question_ids(entry.question_set)),
                "question_ids": list(question_ids(entry.question_set)),
                "shared_question_ids": list(shared_question_ids(entry.question_set)),
                "event_specific_question_ids": list(
                    event_specific_question_ids(entry.question_set)
                ),
                "questionnaire_page": config.questionnaire_page if config else "",
                "overview_page": config.overview_page if config else "",
                "host_page": config.host_page if config else "",
            }
        )
    return rows
