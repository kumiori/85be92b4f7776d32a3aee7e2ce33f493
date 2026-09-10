from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from conference.events import conference_event_context, conference_event_options, event_config_for_session_code
from conference.registry import ResolvedQuestionSetBundle, resolve_question_set_bundle
from conference.session_window import filter_rows_to_session_window


@dataclass(frozen=True)
class HostSnapshot:
    session: dict[str, Any]
    questionnaire: ResolvedQuestionSetBundle
    participants: tuple[dict[str, Any], ...]
    responses: tuple[dict[str, Any], ...]
    submissions: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    locations: tuple[dict[str, Any], ...]
    response_field: tuple[dict[str, Any], ...]
    timeline: tuple[dict[str, Any], ...]
    loaded_at: str


def host_session_options(*, include_test: bool = False) -> list[dict[str, Any]]:
    """Return questionnaire-backed host choices without touching remote storage."""
    options: list[dict[str, Any]] = []
    for context in conference_event_options(include_test=include_test):
        session_code = str(context["session_code"])
        try:
            resolve_question_set_bundle(session_code=session_code)
        except ValueError:
            continue
        options.append({
            "event_slug": str(context.get("event_slug") or ""),
            "session_code": session_code,
            "label": str(context.get("event_label") or context.get("event_slug") or session_code),
            "test_mode": bool(context.get("test_mode")),
        })
    return options


def mask_email(value: Any) -> str:
    email = str(value or "").strip()
    if not email or "@" not in email:
        return "<missing>"
    local, domain = email.rsplit("@", 1)
    if not local or not domain:
        return "<missing>"
    if "." in domain:
        stem, suffix = domain.rsplit(".", 1)
        masked_domain = stem[:1] + ("*" * max(len(stem) - 2, 1)) + stem[-1:] + "." + suffix
    else:
        masked_domain = domain[:1] + ("*" * max(len(domain) - 1, 1))
    return local[:1] + ("*" * max(len(local) - 1, 1)) + "@" + masked_domain


def _has_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _active_questions(bundle: ResolvedQuestionSetBundle) -> list[Any]:
    active_steps = {
        str(step)
        for mode in bundle.question_set.flow_modes.values()
        for step in mode.get("steps", [])
    }
    return [
        question for question in bundle.question_set.questions
        if question.status != "retired" and (not active_steps or question.step in active_steps)
    ]


def _section(bundle: ResolvedQuestionSetBundle, question: Any) -> str:
    return str(question.group or bundle.question_set.step_copy.get(question.step, {}).get("title") or "Questions")


def _density(value: Any, question: Any) -> tuple[float, int | None, int | None]:
    input_type = str(question.input_type or "single")
    if input_type == "multi":
        count = len(value) if isinstance(value, (list, tuple, set)) else (1 if _has_answer(value) else 0)
        maximum = max(int(question.max_select or len(question.options) or 1), 1)
        return min(count / maximum, 1.0), count, None
    if input_type == "text":
        length = len(str(value or "").strip())
        return min(length / 200.0, 1.0), None, length
    return (1.0 if _has_answer(value) else 0.0), None, None


def build_response_field(submissions: Sequence[Mapping[str, Any]], bundle: ResolvedQuestionSetBundle) -> list[dict[str, Any]]:
    questions = _active_questions(bundle)
    records: list[dict[str, Any]] = []
    ordered = sorted(submissions, key=lambda row: str(row.get("submitted_at") or ""))
    for index, item in enumerate(ordered, start=1):
        participant_id = str(item.get("player_id") or item.get("actor_key") or f"participant-{index:02d}")
        flags = item.get("question_flags") if isinstance(item.get("question_flags"), dict) else {}
        skipped_fields = {str(field) for field in item.get("deferred_fields", []) if str(field)}
        signals = [
            order for order, question in enumerate(questions, start=1)
            if _has_answer(item.get(question.field)) or question.field in skipped_fields or question.question_id in flags
        ]
        last_signal = max(signals, default=0)
        complete = bool(str(item.get("submitted_at") or "").strip())
        for order, question in enumerate(questions, start=1):
            answered = _has_answer(item.get(question.field))
            skipped = question.field in skipped_fields
            flagged = question.question_id in flags
            reached = complete or order <= last_signal
            status = "answered" if answered else "skipped" if skipped else "viewed_unanswered" if reached else "not_reached"
            density, selection_count, text_length = _density(item.get(question.field), question)
            records.append({
                "participant_id": participant_id,
                "participant_label": str(item.get("identity") or item.get("alias") or f"P{index:02d}"),
                "question_id": str(question.question_id),
                "question_label": str(question.prompt),
                "question_order": order,
                "section": _section(bundle, question),
                "input_type": str(question.input_type),
                "status": status,
                "response_density": density if answered else 0.0,
                "selection_count": selection_count,
                "text_length": text_length,
                "flagged": flagged,
                "skipped": skipped,
            })
    return records


def cumulative_timeline(submissions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    timestamps: list[datetime] = []
    for row in submissions:
        value = str(row.get("submitted_at") or "").strip()
        if not value:
            continue
        try:
            timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            continue
    timestamps.sort()
    return [{"timestamp": value.isoformat(), "cumulative": index} for index, value in enumerate(timestamps, start=1)]


def _location_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = ast.literal_eval(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}
    return {}


def normalize_locations(submissions: Sequence[Mapping[str, Any]], bundle: ResolvedQuestionSetBundle) -> list[dict[str, Any]]:
    geographic = [q for q in _active_questions(bundle) if q.input_type in {"geography_context", "location"}]
    points: list[dict[str, Any]] = []
    for submission in submissions:
        for question in geographic:
            location = _location_dict(submission.get(question.field))
            coordinates = location.get("coordinates")
            lat = location.get("lat") or location.get("latitude")
            lng = location.get("lng") or location.get("longitude")
            if coordinates and isinstance(coordinates, str) and "," in coordinates:
                lat, lng = coordinates.split(",", 1)
            try:
                lat_value, lng_value = float(lat), float(lng)
            except (TypeError, ValueError):
                continue
            label = str(location.get("display_label") or location.get("geocode_label") or location.get("country_region") or location.get("country") or question.prompt)
            points.append({"lat": lat_value, "lng": lng_value, "name": label, "dimension": str(question.field), "question_id": str(question.question_id), "energy": 16.0})
    return points


def normalize_profile_locations(
    players: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for player in players:
        location = _location_dict(player.get("base_location"))
        try:
            lat = float(location.get("latitude"))
            lng = float(location.get("longitude"))
        except (TypeError, ValueError):
            continue
        points.append(
            {
                "lat": lat,
                "lng": lng,
                "name": str(location.get("display_label") or "Participant base location"),
                "dimension": "participant_base_location",
                "question_id": "",
                "energy": 16.0,
            }
        )
    return points


def _profile_location_label(value: Any) -> str:
    location = _location_dict(value)
    return str(location.get("display_label") or "<missing>")


def normalize_participants(players: Sequence[Mapping[str, Any]], submissions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("id") or ""): dict(item) for item in players if item.get("id")}
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, submission in enumerate(submissions, start=1):
        player_id = str(submission.get("player_id") or submission.get("actor_key") or f"participant-{index:02d}")
        player = by_id.get(player_id, {})
        email = player.get("email") or submission.get("email") or submission.get("contact")
        first = str(submission.get("created_at") or submission.get("submitted_at") or "")
        last = str(submission.get("submitted_at") or submission.get("updated_at") or first)
        output.append({
            "participant_id": player_id,
            "display_name": str(player.get("nickname") or submission.get("identity") or submission.get("alias") or f"P{index:02d}"),
            "email": mask_email(email),
            "institution": str(player.get("institution") or submission.get("institution") or submission.get("scientific_home_institution") or "<missing>"),
            "location": _profile_location_label(player.get("base_location")),
            "submission_status": "completed" if str(submission.get("submitted_at") or "").strip() else "in progress",
            "first_contribution": first or "<missing>",
            "last_contribution": last or "<missing>",
        })
        seen.add(player_id)
    for player_id, player in by_id.items():
        if player_id in seen:
            continue
        output.append({
            "participant_id": player_id,
            "display_name": str(player.get("nickname") or player_id),
            "email": mask_email(player.get("email")),
            "institution": str(player.get("institution") or "<missing>"),
            "location": _profile_location_label(player.get("base_location")),
            "submission_status": "not started",
            "first_contribution": str(player.get("joined_at") or player.get("created_at") or "<missing>"),
            "last_contribution": str(player.get("last_seen") or player.get("last_joined_on") or "<missing>"),
        })
    return output


def snapshot_metrics(snapshot: HostSnapshot) -> dict[str, Any]:
    answered = sum(1 for cell in snapshot.response_field if cell["status"] == "answered")
    completed = sum(1 for participant in snapshot.participants if participant["submission_status"] == "completed")
    latest = max((str(row.get("submitted_at") or "") for row in snapshot.submissions), default="")
    return {"participants": len(snapshot.participants), "completed_submissions": completed, "questions_answered": answered, "last_contribution": latest or "—"}


def load_host_snapshot(
    session_code: str,
    *,
    repo: Any,
    list_players: Callable[[str], Sequence[Mapping[str, Any]]],
    list_events: Callable[[str], Sequence[Mapping[str, Any]]],
    now: Callable[[], datetime] = datetime.now,
) -> HostSnapshot:
    session = repo.resolve_session(session_code=session_code)
    if not session:
        raise ValueError(f"Session {session_code!r} is unavailable.")
    config = event_config_for_session_code(session_code)
    text_ids = config.text_ids if config else ()
    rows = repo.get_session_rows(str(session.get("id") or ""), text_ids=text_ids)
    filtered = filter_rows_to_session_window(list(rows), session)
    submissions = repo.group_rows_by_submission(filtered)
    bundle = resolve_question_set_bundle(session=session)
    players = list(list_players(str(session.get("id") or "")))
    participants = normalize_participants(players, submissions)
    field = build_response_field(submissions, bundle)
    return HostSnapshot(
        session=dict(session), questionnaire=bundle, participants=tuple(participants),
        responses=tuple(filtered), submissions=tuple(submissions),
        events=tuple(dict(item) for item in list_events(str(session.get("id") or ""))),
        locations=tuple([*normalize_profile_locations(players), *normalize_locations(submissions, bundle)]), response_field=tuple(field),
        timeline=tuple(cumulative_timeline(submissions)), loaded_at=now().isoformat(),
    )
