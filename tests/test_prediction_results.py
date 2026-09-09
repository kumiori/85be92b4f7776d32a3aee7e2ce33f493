from types import SimpleNamespace

from conference.prediction_results import build_prediction_results


def _question(**overrides):
    values = {
        "question_id": "q1",
        "field": "systems",
        "prompt": "What systems do you study?",
        "subtitle": "Context from YAML",
        "input_type": "pills",
        "options": (
            {"value": "porous", "label": "Porous media"},
            {"value": "other", "label": "Other"},
        ),
        "free_text_field": "systems_detail",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_prediction_results_keep_answer_skip_and_flag_denominators_separate():
    question = _question()
    submissions = [
        {
            "player_id": "p1",
            "systems": ["porous", "other"],
            "systems_detail": "Synthetic system",
            "question_flags": {"q1": {"flags": ["interesting"]}},
            "question_skips": {},
        },
        {
            "player_id": "p2",
            "systems": [],
            "question_skips": {"q1": {"reasons": []}},
            "question_states": {"q1": {"answer_state": "skipped"}},
        },
    ]

    result = build_prediction_results(submissions, [question])
    signal = result.questions[0]

    assert result.participants == 2
    assert result.submitted_questionnaires == 2
    assert result.scientific_selections == 2
    assert result.skipped_questions == 1
    assert result.flagged_questions == 1
    assert signal.n_answered == 1
    assert signal.n_skipped == 1
    assert signal.n_flagged == 1
    assert signal.counts == (("Porous media", 1), ("Other", 1))
    assert signal.denominator == 1


def test_prediction_text_results_are_anonymous_and_restrained():
    question = _question(
        question_id="q-text",
        field="contribution",
        prompt="What do you put on the table?",
        input_type="text",
        options=(),
        free_text_field="",
    )
    submissions = [
        {"player_id": f"p{i}", "contribution": f"Contribution {i}"}
        for i in range(1, 8)
    ]

    signal = build_prediction_results(submissions, [question]).questions[0]

    assert signal.n_answered == 7
    assert signal.excerpts == tuple(f"Contribution {i}" for i in range(1, 6))
    assert all("p" not in excerpt.lower() for excerpt in signal.excerpts)


def test_prediction_results_do_not_combine_separate_session_inputs():
    question = _question()
    production = build_prediction_results(
        [{"player_id": "prod", "systems": ["porous"]}], [question]
    )
    debug = build_prediction_results(
        [{"player_id": "debug", "systems": ["other"]}], [question]
    )

    assert production.questions[0].counts == (("Porous media", 1), ("Other", 0))
    assert debug.questions[0].counts == (("Porous media", 0), ("Other", 1))
