from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from conference.question_sets import QuestionDefinition, QuestionRevision, QuestionSet


class _QuestionSetYamlLoader(yaml.SafeLoader):
    pass


_QuestionSetYamlLoader.yaml_implicit_resolvers = {
    key: [
        resolver
        for resolver in resolvers
        if resolver[0] != "tag:yaml.org,2002:bool"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return bool(value)


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise ValueError(f"Question set YAML field `{field}` must be a mapping.")


def _as_sequence(value: Any, *, field: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"Question set YAML field `{field}` must be a list.")
    return tuple(value)


def _as_string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    return tuple(str(item) for item in _as_sequence(value, field=field))


def _as_options(value: Any, *, question_id: str) -> tuple[dict[str, str], ...]:
    options = _as_sequence(value, field=f"questions[{question_id}].options")
    out: list[dict[str, str]] = []
    for index, option in enumerate(options):
        if not isinstance(option, Mapping):
            raise ValueError(
                f"Question `{question_id}` option {index + 1} must be a mapping."
            )
        option_value = str(option.get("value") or "").strip()
        option_label = str(option.get("label") or "").strip()
        if not option_value or not option_label:
            raise ValueError(
                f"Question `{question_id}` option {index + 1} needs `value` and `label`."
            )
        out.append({"value": option_value, "label": option_label})
    return tuple(out)


def _merge_shared_question(
    raw: Any,
    *,
    index: int,
    shared_questions: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    question = _as_mapping(raw, field=f"questions[{index}]")
    reference = str(question.get("use") or "").strip()
    if not reference:
        return question
    if reference not in shared_questions:
        raise ValueError(f"Unknown shared question reference `{reference}`.")
    base = dict(shared_questions[reference])
    overrides = {key: value for key, value in question.items() if key != "use"}
    allowed_overrides = {
        "id",
        "revision",
        "legacy_ids",
        "prompt",
        "subtitle",
        "context",
        "required",
        "max_select",
        "group",
        "subgroup",
        "placeholder",
        "skippable",
        "flaggable",
        "status",
        "options",
        "override_reason",
    }
    unsupported = set(overrides) - allowed_overrides
    if unsupported:
        raise ValueError(
            f"Shared question `{reference}` cannot override: {', '.join(sorted(unsupported))}."
        )
    if "options" in overrides and not str(overrides.get("override_reason") or "").strip():
        raise ValueError(
            f"Shared question `{reference}` option overrides require `override_reason`."
        )
    overrides.pop("override_reason", None)
    base.update(overrides)
    base.setdefault("origin", "shared")
    return base


def _question_from_yaml(
    raw: Any,
    *,
    index: int,
    shared_questions: Mapping[str, Mapping[str, Any]] | None = None,
) -> QuestionDefinition:
    question = _merge_shared_question(
        raw, index=index, shared_questions=shared_questions or {}
    )
    question_id = str(question.get("id") or question.get("question_id") or "").strip()
    if not question_id:
        raise ValueError(f"Question {index + 1} is missing `id`.")
    free_text = question.get("free_text") or {}
    if free_text and not isinstance(free_text, Mapping):
        raise ValueError(f"Question `{question_id}` field `free_text` must be a mapping.")
    revision_value = question.get("revision", 1)
    legacy_revision = revision_value if isinstance(revision_value, Mapping) else {}
    change_raw = question.get("change") or legacy_revision or {}
    if change_raw and not isinstance(change_raw, Mapping):
        raise ValueError(f"Question `{question_id}` field `change` must be a mapping.")
    revision_number = 1 if isinstance(revision_value, Mapping) else int(revision_value or 1)
    supersedes_revision = question.get("supersedes_revision")
    revision = None
    if change_raw:
        revision = QuestionRevision(
            supersedes=str(change_raw.get("supersedes") or "").strip(),
            change_type=str(change_raw.get("type") or change_raw.get("change_type") or "copy_only").strip(),
            reason=str(change_raw.get("reason") or "").strip(),
            reask_if_answered=_as_bool(
                change_raw.get("reask_if_answered"), default=False
            ),
            preserve_previous_response=_as_bool(
                change_raw.get("preserve_previous_response"), default=True
            ),
        )
    return QuestionDefinition(
        step=str(question.get("step") or "").strip(),
        field=str(question.get("field") or "").strip(),
        question_id=question_id,
        prompt=str(question.get("prompt") or "").strip(),
        subtitle=str(
            question.get("subtitle")
            or question.get("context")
            or ""
        ).strip(),
        input_type=str(question.get("input_type") or "single").strip(),
        options=_as_options(question.get("options"), question_id=question_id),
        required=_as_bool(question.get("required"), default=False),
        max_select=(
            int(question["max_select"])
            if question.get("max_select") not in (None, "")
            else None
        ),
        placeholder=str(question.get("placeholder") or "").strip(),
        origin=str(question.get("origin") or "event").strip(),
        group=str(question.get("group") or "").strip(),
        subgroup=str(question.get("subgroup") or "").strip(),
        free_text_field=str(free_text.get("field") or "").strip(),
        free_text_label=str(free_text.get("label") or "").strip(),
        free_text_placeholder=str(free_text.get("placeholder") or "").strip(),
        free_text_required=_as_bool(free_text.get("required"), default=False),
        revision=revision,
        revision_number=revision_number,
        supersedes_revision=(
            int(supersedes_revision)
            if supersedes_revision not in (None, "")
            else None
        ),
        status=str(question.get("status") or "active").strip(),
        shared_dimension=str(
            question.get("shared_dimension") or question.get("semantic_axis") or ""
        ).strip(),
        legacy_ids=_as_string_tuple(
            question.get("legacy_ids"), field=f"questions[{question_id}].legacy_ids"
        ),
        skippable=_as_bool(question.get("skippable"), default=True),
        flaggable=_as_bool(question.get("flaggable"), default=True),
    )


def question_set_from_yaml(
    payload: Mapping[str, Any],
    *,
    source_module: str,
    shared_questions: Mapping[str, Mapping[str, Any]] | None = None,
) -> QuestionSet:
    """Build a runtime QuestionSet from the author-facing YAML contract."""
    meta = _as_mapping(
        payload.get("questionnaire") or payload.get("question_set") or {},
        field="questionnaire",
    )
    question_set_id = str(meta.get("id") or "").strip()
    if not question_set_id:
        raise ValueError("Questionnaire YAML needs `questionnaire.id`.")
    review = _as_mapping(meta.get("review") or {}, field="questionnaire.review")

    return QuestionSet(
        id=question_set_id,
        source_module=source_module,
        step_copy=_as_mapping(payload.get("step_copy") or {}, field="step_copy"),
        step_order=_as_string_tuple(payload.get("step_order"), field="step_order"),
        flow_modes=_as_mapping(payload.get("flow_modes") or {}, field="flow_modes"),
        questions=tuple(
            _question_from_yaml(raw, index=index, shared_questions=shared_questions)
            for index, raw in enumerate(
                _as_sequence(payload.get("questions"), field="questions")
            )
        ),
        profile_fields=_as_string_tuple(
            payload.get("profile_fields"),
            field="profile_fields",
        ),
        session_fields=_as_string_tuple(
            payload.get("session_fields"),
            field="session_fields",
        ),
        deferrable_fields=_as_string_tuple(
            payload.get("deferrable_fields"),
            field="deferrable_fields",
        ),
        fingerprint_axes=_as_string_tuple(
            payload.get("fingerprint_axes"),
            field="fingerprint_axes",
        ),
        fingerprint_labels={
            str(key): str(value)
            for key, value in _as_mapping(
                payload.get("fingerprint_labels") or {},
                field="fingerprint_labels",
            ).items()
        },
        follow_up_contact_values=_as_string_tuple(
            payload.get("follow_up_contact_values"),
            field="follow_up_contact_values",
        ),
        migration_profile_fields=_as_string_tuple(
            payload.get("migration_profile_fields"),
            field="migration_profile_fields",
        ),
        default_mode=str(meta.get("default_mode") or "quick").strip(),
        show_mode_selection=_as_bool(meta.get("show_mode_selection"), default=True),
        show_welcome_step=_as_bool(meta.get("show_welcome_step"), default=True),
        identity_position=str(meta.get("identity_position") or "last").strip(),
        source_kind="yaml",
        source_path=str(meta.get("source_path") or "").strip(),
        source_note=str(meta.get("source_note") or "").strip(),
        version=str(meta.get("version") or meta.get("revision") or "1").strip(),
        schema_id=str(meta.get("schema_id") or "").strip(),
        legacy_questions=tuple(
            _question_from_yaml(raw, index=index, shared_questions=shared_questions)
            for index, raw in enumerate(
                _as_sequence(payload.get("legacy_questions"), field="legacy_questions")
            )
        ),
        revision=int(meta.get("revision") or meta.get("version") or 1),
        format=int(meta.get("format") or 2),
        status=str(meta.get("status") or "active").strip(),
        reviewed_at=str(review.get("reviewed_at") or "").strip(),
        reviewed_by=_as_string_tuple(review.get("reviewed_by"), field="questionnaire.review.reviewed_by"),
        change_note=str(review.get("change_note") or "").strip(),
        legacy_questionnaire_ids=_as_string_tuple(
            meta.get("legacy_ids"), field="questionnaire.legacy_ids"
        ),
    )


def load_question_set_yaml(path: str | Path, *, source_module: str) -> QuestionSet:
    yaml_path = Path(path)
    with yaml_path.open("r", encoding="utf-8") as handle:
        payload = yaml.load(handle, Loader=_QuestionSetYamlLoader) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"Question set YAML `{yaml_path}` must contain a mapping.")
    normalized_payload = dict(payload)
    meta_key = "questionnaire" if "questionnaire" in normalized_payload else "question_set"
    meta = dict(normalized_payload.get(meta_key) or {})
    meta["source_path"] = str(yaml_path.resolve())
    meta.setdefault("source_note", "Loaded from YAML question-set spec.")
    normalized_payload[meta_key] = meta
    shared_path = Path(__file__).with_name("shared_questions.yaml")
    shared_questions: Mapping[str, Mapping[str, Any]] = {}
    if shared_path.exists():
        with shared_path.open("r", encoding="utf-8") as handle:
            shared_payload = yaml.load(handle, Loader=_QuestionSetYamlLoader) or {}
        shared_questions = _as_mapping(
            shared_payload.get("questions") or {}, field="shared questions"
        )
    return question_set_from_yaml(
        normalized_payload,
        source_module=source_module,
        shared_questions=shared_questions,
    )
