from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from conference.question_sets import QuestionDefinition, QuestionSet, question_by_id


def _blocks(bundle: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    profile = bundle.get("profile")
    session = bundle.get("session")
    return (
        profile if isinstance(profile, Mapping) else {},
        session if isinstance(session, Mapping) else {},
    )


def _value_for(bundle: Mapping[str, Any], field: str) -> Any:
    profile, session = _blocks(bundle)
    if field in profile:
        return profile.get(field)
    if field in session:
        return session.get(field)
    return bundle.get(field)


def _answered(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_answered(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_answered(item) for item in value)
    return bool(str(value or "").strip())


def _answer_label(question: QuestionDefinition | None, value: Any) -> str:
    if not question:
        return str(value or "")
    labels = {str(item["value"]): str(item["label"]) for item in question.options}
    if isinstance(value, (list, tuple)):
        return ", ".join(labels.get(str(item), str(item)) for item in value)
    return labels.get(str(value), str(value or ""))


def _completed_refinement_ids(bundle: Mapping[str, Any]) -> set[str]:
    _, session = _blocks(bundle)
    refinements = session.get("response_refinements")
    if not isinstance(refinements, list):
        return set()
    return {
        str(item.get("question_id") or "").strip()
        for item in refinements
        if isinstance(item, Mapping) and str(item.get("question_id") or "").strip()
    }


def _bundle_schema_tokens(bundle: Mapping[str, Any]) -> set[str]:
    """Return explicit schema/version markers carried by a response bundle."""
    _, session = _blocks(bundle)
    return {
        str(value).strip()
        for value in (
            bundle.get("schema_id"),
            bundle.get("questionnaire_version"),
            session.get("schema_id"),
            session.get("questionnaire_version"),
        )
        if str(value or "").strip()
    }


def compare_response_bundle_to_schema(
    *,
    player_id: str,
    response_bundle: Mapping[str, Any],
    current_schema: QuestionSet,
    previous_response_id: str = "",
) -> dict[str, list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    needs_refinement: list[dict[str, Any]] = []
    new_questions: list[dict[str, Any]] = []
    legacy_only: list[dict[str, Any]] = []
    completed = _completed_refinement_ids(response_bundle)
    response_schema_tokens = _bundle_schema_tokens(response_bundle)
    is_current_schema = bool(
        response_schema_tokens
        & {str(current_schema.schema_id).strip(), str(current_schema.version).strip()}
    )

    for question in current_schema.questions:
        value = _value_for(response_bundle, question.field)
        revision = question.revision
        old_question = (
            question_by_id(
                current_schema,
                revision.supersedes,
                include_legacy=True,
            )
            if revision
            else None
        )
        item = {
            "player_id": str(player_id or ""),
            "question_id": question.question_id,
            "field": question.field,
            "question": question.prompt,
            "answer": deepcopy(value),
            "answer_label": _answer_label(question, value),
            "previous_response_id": str(previous_response_id or ""),
        }
        requires_refinement = bool(
            revision
            and revision.requires_reanswer
            and _answered(value)
            and not is_current_schema
            and question.question_id not in completed
        )
        if requires_refinement:
            needs_refinement.append(
                {
                    **item,
                    "previous_question_id": revision.supersedes,
                    "previous_question": old_question.prompt if old_question else "",
                    "previous_answer": deepcopy(value),
                    "previous_answer_label": _answer_label(old_question, value),
                    "reason": revision.reason,
                    "change_type": revision.change_type,
                }
            )
        elif _answered(value):
            current.append(item)
        else:
            new_questions.append(item)

    superseded = {
        question.revision.supersedes
        for question in current_schema.questions
        if question.revision
    }
    for question in current_schema.legacy_questions:
        value = _value_for(response_bundle, question.field)
        if _answered(value) and question.question_id not in superseded:
            legacy_only.append(
                {
                    "question_id": question.question_id,
                    "field": question.field,
                    "question": question.prompt,
                    "answer": deepcopy(value),
                    "answer_label": _answer_label(question, value),
                }
            )

    return {
        "current": current,
        "needs_refinement": needs_refinement,
        "new_questions": new_questions,
        "legacy_only": legacy_only,
    }


def build_refinement_bundle(
    *,
    previous_bundle: Mapping[str, Any],
    question: QuestionDefinition,
    current_schema: QuestionSet,
    answer: Any,
    previous_response_id: str,
    refined_at: str = "",
) -> dict[str, Any]:
    revision = question.revision
    if not revision or not revision.requires_reanswer:
        raise ValueError("Question does not define a semantic refinement.")
    refined = deepcopy(dict(previous_bundle))
    profile = dict(refined.get("profile") or {})
    session = dict(refined.get("session") or {})
    previous_answer = _value_for(previous_bundle, question.field)
    target = profile if question.field in set(current_schema.profile_fields) else session
    target[question.field] = deepcopy(answer)
    profile["persistence_scope"] = str(
        profile.get("persistence_scope") or "persistent_profile"
    )
    session["schema_id"] = current_schema.schema_id
    session["questionnaire_version"] = current_schema.version
    history = list(session.get("response_refinements") or [])
    history.append(
        {
            "kind": "response_refinement",
            "question_id": question.question_id,
            "supersedes": revision.supersedes,
            "change_type": revision.change_type,
            "reason": revision.reason,
            "preserve_previous_response": revision.preserve_previous_response,
            "previous_response_id": str(previous_response_id or ""),
            "previous_answer": deepcopy(previous_answer),
            "answer": deepcopy(answer),
            "refined_at": str(refined_at or "").strip()
            or datetime.now(timezone.utc).isoformat(),
        }
    )
    session["response_refinements"] = history
    refined["profile"] = profile
    refined["session"] = session
    return refined
