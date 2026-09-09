from conference.question_flags import QUESTION_FLAG_LABELS, QUESTION_FLAG_OPTIONS
from conference.question_skips import (
    QUESTION_SKIP_LABELS,
    QUESTION_SKIP_OPTIONS,
    normalize_question_skips,
)
from conference.question_state import answer_question, flag_question, question_state, skip_question


def test_flag_feedback_supports_positive_and_critical_reasons():
    assert [item["label"] for item in QUESTION_FLAG_OPTIONS] == [
        "Interesting",
        "Useful",
        "Thought-provoking",
        "Well framed",
        "Incomplete",
        "Misleading",
        "Too narrow",
        "Unclear",
        "Missing option",
    ]
    assert QUESTION_FLAG_LABELS["interesting_question"] == "Interesting"


def test_skip_has_its_own_response_reasons():
    assert [item["label"] for item in QUESTION_SKIP_OPTIONS] == [
        "Not relevant to me",
        "I don't know",
        "I prefer not to answer",
        "I don't understand the question",
        "None of the options fit",
        "Too difficult to answer briefly",
        "Other",
    ]
    assert "interesting_question" not in QUESTION_SKIP_LABELS
    assert "misleading" not in QUESTION_SKIP_LABELS


def test_skip_reason_is_optional_and_separate_from_flag_metadata():
    assert normalize_question_skips({"q1": {"reasons": [], "note": ""}}) == {}
    assert normalize_question_skips(
        {"q1": {"reasons": ["dont_know"], "note": ""}}
    ) == {"q1": {"reasons": ["dont_know"], "note": ""}}


def test_answer_and_skip_states_each_coexist_with_flag_state():
    answered_flagged = flag_question(answer_question({}, "q1"), "q1", flagged=True)
    skipped_flagged = flag_question(skip_question({}, "q1"), "q1", flagged=True)

    assert question_state(answered_flagged, "q1") == {
        "answer_state": "answered",
        "flagged": True,
    }
    assert question_state(skipped_flagged, "q1") == {
        "answer_state": "skipped",
        "flagged": True,
    }
