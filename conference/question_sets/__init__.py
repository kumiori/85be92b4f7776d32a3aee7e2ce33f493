from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


REVISION_CHANGE_TYPES = {
    "copy_only",
    "options_changed",
    "split",
    "merged",
    "semantic_change",
}


@dataclass(frozen=True)
class QuestionRevision:
    supersedes: str
    change_type: str
    reason: str
    reask_if_answered: bool = False
    preserve_previous_response: bool = True

    @property
    def requires_reanswer(self) -> bool:
        return bool(
            self.reask_if_answered
            and self.change_type in {
                "options_changed",
                "split",
                "merged",
                "semantic_change",
            }
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "supersedes": self.supersedes,
            "change_type": self.change_type,
            "reason": self.reason,
            "reask_if_answered": self.reask_if_answered,
            "preserve_previous_response": self.preserve_previous_response,
        }


@dataclass(frozen=True)
class QuestionDefinition:
    step: str
    field: str
    question_id: str
    prompt: str
    subtitle: str = ""
    input_type: str = "single"
    options: tuple[dict[str, str], ...] = ()
    required: bool = False
    max_select: int | None = None
    placeholder: str = ""
    origin: str = "event"
    group: str = ""
    subgroup: str = ""
    free_text_field: str = ""
    free_text_label: str = ""
    free_text_placeholder: str = ""
    free_text_required: bool = False
    revision: QuestionRevision | None = None
    skippable: bool = True
    flaggable: bool = True
    revision_number: int = 1
    supersedes_revision: int | None = None
    status: str = "active"
    shared_dimension: str = ""
    legacy_ids: tuple[str, ...] = ()

    @property
    def context(self) -> str:
        return self.subtitle

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "step": self.step,
            "field": self.field,
            "question_id": self.question_id,
            "prompt": self.prompt,
            "subtitle": self.subtitle,
            "context": self.context,
            "input_type": self.input_type,
            "options": [dict(item) for item in self.options],
            "required": self.required,
            "status": self.status,
        }
        if self.max_select is not None:
            out["max_select"] = self.max_select
        if self.placeholder:
            out["placeholder"] = self.placeholder
        if self.group:
            out["group"] = self.group
        if self.subgroup:
            out["subgroup"] = self.subgroup
        if self.free_text_field:
            out["free_text"] = {
                "field": self.free_text_field,
                "label": self.free_text_label,
                "placeholder": self.free_text_placeholder,
                "required": self.free_text_required,
            }
        if (
            self.revision
            and self.revision.supersedes
            and self.supersedes_revision is None
            and self.revision_number == 1
        ):
            out["revision"] = self.revision.as_dict()
        else:
            out["revision"] = self.revision_number
            if self.revision:
                out["revision_lineage"] = self.revision.as_dict()
        if self.supersedes_revision is not None:
            out["supersedes_revision"] = self.supersedes_revision
        if self.shared_dimension:
            out["shared_dimension"] = self.shared_dimension
        if self.legacy_ids:
            out["legacy_ids"] = list(self.legacy_ids)
        out["interactions"] = question_interactions(self)
        return out


@dataclass(frozen=True)
class StepInteractions:
    can_flag: bool
    can_skip: bool
    flag_reason_disabled: str = ""
    skip_reason_disabled: str = ""

    def as_dict(self) -> dict[str, bool | str]:
        return {
            "can_flag": self.can_flag,
            "can_skip": self.can_skip,
            "flag_reason_disabled": self.flag_reason_disabled,
            "skip_reason_disabled": self.skip_reason_disabled,
        }


IDENTITY_SKIP_DISABLED_REASON = (
    "At this stage, this is required to continue. If you think this is too "
    "restrictive, drop us a message."
)


def step_interactions(
    step: str, *, question: QuestionDefinition | None = None
) -> StepInteractions:
    """Return the visible Flag/Skip capability contract for any rendered step."""
    if question is not None:
        return StepInteractions(
            can_flag=bool(question.flaggable),
            can_skip=bool(question.skippable),
            flag_reason_disabled="Flagging is not available for this step."
            if not question.flaggable
            else "",
            skip_reason_disabled="This step is required to continue."
            if not question.skippable
            else "",
        )
    if step == "identity":
        return StepInteractions(
            can_flag=True,
            can_skip=False,
            skip_reason_disabled=IDENTITY_SKIP_DISABLED_REASON,
        )
    if step == "review":
        return StepInteractions(
            can_flag=False,
            can_skip=False,
            flag_reason_disabled="Return to a step to flag it.",
            skip_reason_disabled="Review cannot be skipped; submit or return to a step.",
        )
    return StepInteractions(
        can_flag=False,
        can_skip=False,
        flag_reason_disabled="Flagging is not available for this step.",
        skip_reason_disabled="Skipping is not available for this step.",
    )


def question_interactions(question: QuestionDefinition) -> dict[str, bool | str]:
    """Platform interaction contract for every configured scientific question."""
    return step_interactions(str(question.step), question=question).as_dict()


@dataclass(frozen=True)
class QuestionSet:
    id: str
    source_module: str
    step_copy: Mapping[str, Mapping[str, str]]
    step_order: Sequence[str]
    flow_modes: Mapping[str, Mapping[str, Any]]
    questions: Sequence[QuestionDefinition]
    profile_fields: Sequence[str]
    session_fields: Sequence[str]
    deferrable_fields: Sequence[str]
    fingerprint_axes: Sequence[str]
    fingerprint_labels: Mapping[str, str]
    follow_up_contact_values: Sequence[str]
    migration_profile_fields: Sequence[str]
    default_mode: str = "quick"
    show_mode_selection: bool = True
    show_welcome_step: bool = True
    identity_position: str = "last"
    source_kind: str = "python"
    source_path: str = ""
    source_note: str = ""
    version: str = "1"
    schema_id: str = ""
    legacy_questions: Sequence[QuestionDefinition] = ()
    revision: int = 1
    format: int = 2
    status: str = "active"
    reviewed_at: str = ""
    reviewed_by: Sequence[str] = ()
    change_note: str = ""
    legacy_questionnaire_ids: Sequence[str] = ()


def question_ids(question_set: QuestionSet) -> list[str]:
    return [
        question.question_id
        for question in question_set.questions
        if question.status != "retired"
    ]


def active_questions(question_set: QuestionSet) -> list[QuestionDefinition]:
    return [question for question in question_set.questions if question.status != "retired"]


def questionnaire_is_participant_facing(question_set: QuestionSet) -> bool:
    return question_set.status == "active"


def question_requires_reanswer(
    previous: QuestionDefinition,
    current: QuestionDefinition,
) -> bool:
    if previous.question_id != current.question_id:
        return False
    if current.revision_number <= previous.revision_number:
        return False
    if current.supersedes_revision not in {None, previous.revision_number}:
        return False
    return bool(current.revision and current.revision.reask_if_answered)


def questions_requiring_reanswer(
    question_set: QuestionSet,
    stored_provenance: Mapping[str, Any],
) -> list[QuestionDefinition]:
    required: list[QuestionDefinition] = []
    for current in active_questions(question_set):
        prior = stored_provenance.get(current.question_id)
        if not isinstance(prior, Mapping):
            continue
        prior_revision = int(prior.get("question_revision") or 1)
        if (
            current.revision_number > prior_revision
            and current.supersedes_revision in {None, prior_revision}
            and current.revision
            and current.revision.reask_if_answered
        ):
            required.append(current)
    return required


def question_by_step(
    question_set: QuestionSet,
    step: str,
) -> QuestionDefinition | None:
    token = str(step or "").strip()
    for question in active_questions(question_set):
        if question.step == token:
            return question
    return None


def question_by_field(
    question_set: QuestionSet,
    field: str,
) -> QuestionDefinition | None:
    token = str(field or "").strip()
    for question in active_questions(question_set):
        if question.field == token:
            return question
    return None


def question_by_id(
    question_set: QuestionSet,
    question_id: str,
    *,
    include_legacy: bool = False,
) -> QuestionDefinition | None:
    token = str(question_id or "").strip()
    questions = list(question_set.questions)
    if include_legacy:
        questions.extend(question_set.legacy_questions)
    for question in questions:
        if question.question_id == token or token in question.legacy_ids:
            return question
    return None


def field_for_step(question_set: QuestionSet, step: str) -> str:
    question = question_by_step(question_set, step)
    return str(question.field) if question else ""


def field_option_label_map(
    question_set: QuestionSet,
    field: str,
) -> dict[str, str]:
    question = question_by_field(question_set, field)
    if not question:
        return {}
    return {
        str(option["value"]): str(option["label"])
        for option in question.options
    }


def field_value_set(question_set: QuestionSet, field: str) -> set[str]:
    question = question_by_field(question_set, field)
    if not question:
        return set()
    return {str(option["value"]) for option in question.options}


def active_steps_for_mode(question_set: QuestionSet, mode: str) -> list[str]:
    spec = question_set.flow_modes.get(str(mode or "").strip())
    if not spec:
        return []
    return [str(step) for step in spec.get("steps", []) if str(step).strip()]


def mode_card_rows(question_set: QuestionSet) -> list[dict[str, str]]:
    return [
        {
            "value": key,
            "title": str(item["title"]),
            "detail": str(item["detail"]),
            "accent": str(item["accent"]),
        }
        for key, item in question_set.flow_modes.items()
    ]


def shared_question_ids(question_set: QuestionSet) -> list[str]:
    return [question.question_id for question in question_set.questions if question.origin == "shared"]


def event_specific_question_ids(question_set: QuestionSet) -> list[str]:
    return [question.question_id for question in question_set.questions if question.origin != "shared"]


def questions_as_dicts(question_set: QuestionSet) -> list[dict[str, Any]]:
    return [question.as_dict() for question in question_set.questions]


def step_copy_dict(question_set: QuestionSet) -> dict[str, dict[str, str]]:
    return {
        str(step): {str(key): str(value) for key, value in copy.items()}
        for step, copy in question_set.step_copy.items()
    }


def validate_question_set(question_set: QuestionSet) -> list[str]:
    errors: list[str] = []
    if question_set.status not in {"draft", "review", "active", "archived"}:
        errors.append(f"Unknown questionnaire status in {question_set.id}: {question_set.status}")
    if int(question_set.revision) < 1:
        errors.append(f"Questionnaire revision must be positive in {question_set.id}")
    seen_ids: set[str] = set()
    seen_steps: set[str] = set()
    step_order = {str(step) for step in question_set.step_order}
    built_in_steps = {"welcome", "identity", "review", "done"}
    for question in question_set.questions:
        if question.status not in {"active", "retired"}:
            errors.append(
                f"Unknown question status in {question_set.id}: {question.status}"
            )
        if question.revision_number < 1:
            errors.append(
                f"Question revision must be positive in {question_set.id}: {question.question_id}"
            )
        if question.question_id in seen_ids:
            errors.append(f"Duplicate question id in {question_set.id}: {question.question_id}")
        seen_ids.add(question.question_id)
        if question.step in seen_steps:
            errors.append(f"Duplicate step in {question_set.id}: {question.step}")
        seen_steps.add(question.step)
        if question.step not in step_order:
            errors.append(f"Question step missing from step_order in {question_set.id}: {question.step}")
        revision = question.revision
        if revision:
            if revision.change_type not in REVISION_CHANGE_TYPES:
                errors.append(
                    f"Unknown revision change type in {question_set.id}: "
                    f"{revision.change_type}"
                )
            if not revision.supersedes:
                errors.append(
                    f"Revision missing supersedes in {question_set.id}: "
                    f"{question.question_id}"
                )
            if revision.supersedes == question.question_id:
                errors.append(
                    f"Question cannot supersede itself in {question_set.id}: "
                    f"{question.question_id}"
                )
    legacy_ids = {question.question_id for question in question_set.legacy_questions}
    for question in question_set.questions:
        revision = question.revision
        if revision and revision.supersedes not in legacy_ids:
            errors.append(
                f"Revision target missing from legacy questions in {question_set.id}: "
                f"{revision.supersedes}"
            )
    for mode, payload in question_set.flow_modes.items():
        for step in payload.get("steps", []):
            token = str(step)
            if token in built_in_steps:
                continue
            if token not in seen_steps:
                errors.append(f"Mode {mode} references unknown step in {question_set.id}: {step}")
    return errors


def merge_questions(*groups: Iterable[QuestionDefinition]) -> tuple[QuestionDefinition, ...]:
    out: List[QuestionDefinition] = []
    for group in groups:
        out.extend(list(group))
    return tuple(out)
