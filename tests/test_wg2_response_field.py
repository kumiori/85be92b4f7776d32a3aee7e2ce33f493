from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.question_sets import QuestionDefinition, QuestionSet
from conference.question_sets.un_wg2_v1 import QUESTION_SET as UN_WG2_V1_QUESTION_SET


def _load_overview_module():
    path = ROOT / "pages" / "26_UN_WG2_Overview.py"
    spec = importlib.util.spec_from_file_location("wg2_overview_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


OVERVIEW = _load_overview_module()


def _bundle(*questions: QuestionDefinition):
    steps = [question.step for question in questions]
    return SimpleNamespace(
        question_set=QuestionSet(
            id="test",
            source_module="test",
            step_copy={question.step: {"title": question.group or "I. Test"} for question in questions},
            step_order=steps,
            flow_modes={"quick": {"steps": steps}},
            questions=questions,
            profile_fields=[],
            session_fields=[],
            deferrable_fields=[],
            fingerprint_axes=[],
            fingerprint_labels={},
            follow_up_contact_values=[],
            migration_profile_fields=[],
        )
    )


def test_response_field_single_choice_density():
    question = QuestionDefinition(
        step="choice",
        field="choice",
        question_id="Q_SINGLE",
        prompt="Pick one",
        input_type="single",
    )

    records = OVERVIEW.build_response_field_records(
        [{"choice": "yes", "submitted_at": "2026-07-20T12:00:00Z"}],
        _bundle(question),
    )

    assert records[0]["status"] == "answered"
    assert records[0]["response_density"] == 1.0


def test_response_field_multiselect_normalization():
    question = QuestionDefinition(
        step="multi",
        field="multi",
        question_id="Q_MULTI",
        prompt="Pick several",
        input_type="multi",
        max_select=4,
    )

    records = OVERVIEW.build_response_field_records(
        [{"multi": ["a", "b"], "submitted_at": "2026-07-20T12:00:00Z"}],
        _bundle(question),
    )

    assert records[0]["selection_count"] == 2
    assert records[0]["response_density"] == 0.5


def test_response_field_text_length_buckets():
    question = QuestionDefinition(
        step="text",
        field="text",
        question_id="Q_TEXT",
        prompt="Write",
        input_type="text",
    )
    bundle = _bundle(question)

    short = OVERVIEW.build_response_field_records(
        [{"text": "short", "submitted_at": "2026-07-20T12:00:00Z"}],
        bundle,
    )[0]
    long = OVERVIEW.build_response_field_records(
        [{"text": "x" * 201, "submitted_at": "2026-07-20T12:00:00Z"}],
        bundle,
    )[0]

    assert short["text_length"] == 5
    assert short["response_density"] == 0.25
    assert long["response_density"] == 1.0


def test_response_field_skip_is_distinct_from_unanswered():
    question = QuestionDefinition(
        step="choice",
        field="choice",
        question_id="Q_SKIP",
        prompt="Pick one",
        input_type="single",
    )

    records = OVERVIEW.build_response_field_records(
        [{"deferred_fields": ["choice"], "submitted_at": "2026-07-20T12:00:00Z"}],
        _bundle(question),
    )

    assert records[0]["status"] == "skipped"
    assert records[0]["skipped"] is True
    assert records[0]["response_density"] == 0.0


def test_response_field_flagged_overlay_state():
    question = QuestionDefinition(
        step="choice",
        field="choice",
        question_id="Q_FLAG",
        prompt="Pick one",
        input_type="single",
    )

    records = OVERVIEW.build_response_field_records(
        [
            {
                "choice": "yes",
                "question_flags": {"Q_FLAG": {"flags": ["unclear"], "note": ""}},
                "submitted_at": "2026-07-20T12:00:00Z",
            }
        ],
        _bundle(question),
    )

    assert records[0]["status"] == "answered"
    assert records[0]["flagged"] is True


def test_response_field_uses_question_order_from_yaml():
    bundle = SimpleNamespace(question_set=UN_WG2_V1_QUESTION_SET)
    submissions = [{"wg2_role_lens": ["modeller"], "submitted_at": "2026-07-20T12:00:00Z"}]

    records = OVERVIEW.build_response_field_records(submissions, bundle)
    ordered_ids = [record["question_id"] for record in records]

    assert ordered_ids == [
        question.question_id for question in OVERVIEW._active_questions(bundle)
    ]
    assert ordered_ids[0] == "UN_WG2_ROLE_LENS"


def test_response_field_partial_route_marks_later_questions_not_reached():
    first = QuestionDefinition(
        step="first",
        field="first",
        question_id="Q_FIRST",
        prompt="First",
        input_type="single",
    )
    second = QuestionDefinition(
        step="second",
        field="second",
        question_id="Q_SECOND",
        prompt="Second",
        input_type="single",
    )

    records = OVERVIEW.build_response_field_records([{"first": "yes"}], _bundle(first, second))

    assert records[0]["status"] == "answered"
    assert records[1]["status"] == "not_reached"
    assert records[1]["reached"] is False


def test_response_field_geography_excludes_optional_coordinates():
    question = QuestionDefinition(
        step="geo",
        field="geo",
        question_id="Q_GEO",
        prompt="Where?",
        input_type="geography_context",
    )

    records = OVERVIEW.build_response_field_records(
        [
            {
                "geo": {
                    "country_region": "France",
                    "institution_location": "UNESCO Paris",
                    "coordinates": "",
                    "coordinates_consent": "",
                },
                "submitted_at": "2026-07-20T12:00:00Z",
            }
        ],
        _bundle(question),
    )

    assert records[0]["status"] == "answered"
    assert records[0]["response_density"] == 1.0


def test_wg2_base_locations_are_globe_pins():
    places, points = OVERVIEW._base_locations(
        [
            {
                "wg2_main_location": {
                    "country_region": "France",
                    "institution_location": "UNESCO Paris",
                    "coordinates": "48.849, 2.306",
                    "coordinates_consent": "lookup",
                }
            },
            {
                "wg2_main_location": {
                    "country_region": "France",
                    "institution_location": "UNESCO Paris",
                    "coordinates": "48.849, 2.306",
                    "coordinates_consent": "lookup",
                }
            },
        ]
    )

    assert places["France"] == 2
    assert points == [
        {
            "lat": 48.849,
            "lng": 2.306,
            "energy": 24.0,
            "count": 2.0,
            "name": "France · 2 participants",
        }
    ]


def test_wg2_response_timeline_is_cumulative():
    points = OVERVIEW._cumulative_submission_points(
        [
            {"submitted_at": "2026-07-20T12:00:00Z"},
            {"submitted_at": "2026-07-13T09:30:00+00:00"},
            {"submitted_at": ""},
        ]
    )

    assert [point["timestamp"].isoformat() for point in points] == [
        "2026-07-13T09:30:00+00:00",
        "2026-07-20T12:00:00+00:00",
    ]
    assert [point["cumulative"] for point in points] == [1, 2]


def test_wg2_response_timeline_marks_weeks_and_months():
    points = OVERVIEW._cumulative_submission_points(
        [
            {"submitted_at": "2026-07-20T12:00:00Z"},
            {"submitted_at": "2026-08-03T12:00:00Z"},
        ]
    )
    start, end = OVERVIEW._timeline_domain(points)
    weeks = OVERVIEW._timeline_week_ticks(start, end)
    months = OVERVIEW._timeline_month_ticks(start, end)

    assert [week.weekday() for week in weeks] == [0] * len(weeks)
    assert weeks[0].strftime("%Y-%m-%d") == "2026-07-20"
    assert [month.strftime("%Y-%m") for month in months] == ["2026-08"]
