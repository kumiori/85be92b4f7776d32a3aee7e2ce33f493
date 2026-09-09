from __future__ import annotations

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.editorial_results_ui import (
    PAPER_CSS,
    apply_editorial_results_theme,
    render_bars,
    render_excerpts,
    render_metric,
    render_prose,
    render_two_column_section,
)
from conference.events import event_config_for_request, text_ids_for_session_code
from conference.prediction_results import PredictionResults, build_prediction_results
from conference.question_sets import active_questions
from conference.registry import resolve_question_set_bundle
from ui import set_page, stylable_container


def _render_opening(config, results: PredictionResults) -> None:
    result_config = config.result_config
    if config.test_mode:
        st.markdown(
            "<div class='portrait-kicker'>TEST MODE · isolated debug results</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        f"<div class='portrait-kicker'>{result_config.kicker}</div>",
        unsafe_allow_html=True,
    )
    st.title(result_config.headline)
    st.caption(f"{config.title} · {config.place} · {config.dates}")
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
        with stylable_container(key="prediction-opening-copy", css_styles=PAPER_CSS):
            st.caption("Collective scientific portrait")
            render_prose(result_config.introduction)
    with right:
        with stylable_container(key="prediction-opening-signals", css_styles=PAPER_CSS):
            st.caption("Signals at a glance")
            first, second = st.columns(2)
            with first:
                render_metric(results.participants, "participants")
                render_metric(results.scientific_selections, "scientific answers / selections")
                render_metric(results.flagged_questions, "flagged questions")
            with second:
                render_metric(results.submitted_questionnaires, "submitted questionnaires")
                render_metric(results.skipped_questions, "skipped questions")
    st.markdown("<div style='height:4rem'></div>", unsafe_allow_html=True)


def _render_question(signal, prompt: str, index: int) -> None:
    st.markdown(
        f"<div class='portrait-kicker'>Signal {index:02d}</div>",
        unsafe_allow_html=True,
    )
    st.header(signal.prompt)
    if signal.context:
        st.markdown(f"<p class='portrait-copy'>{signal.context}</p>", unsafe_allow_html=True)

    def interpretation() -> None:
        st.caption("Reading the signal")
        st.markdown("### What does this distribution tell us about the room?")
        if prompt:
            st.markdown(f"<p class='portrait-copy'>{prompt}</p>", unsafe_allow_html=True)
        st.caption("Interpretation will be authored after reading the session data.")

    def data() -> None:
        st.caption("Collective signal")
        if signal.input_type == "text":
            render_excerpts(signal.excerpts, signal.n_answered)
        else:
            render_bars(signal.counts, signal.denominator)
        st.markdown(
            f'<div class="portrait-meta">{signal.n_participants} participants · '
            f'{signal.n_answered} answered · {signal.n_skipped} skipped · '
            f'{signal.n_flagged} flagged</div>',
            unsafe_allow_html=True,
        )

    render_two_column_section(
        key=f"prediction-{signal.question_id}",
        interpretation=interpretation,
        data=data,
        data_left=index % 2 == 0,
    )


def main() -> None:
    set_page()
    apply_editorial_results_theme()
    slug = str(st.query_params.get("event") or "prediction").strip().lower()
    config = event_config_for_request(slug, test=st.query_params.get("test", ""))
    if not config or not str(config.slug).startswith("prediction"):
        st.error("Unknown Prediction event.")
        return
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=config.session_code)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    if not repo or not session:
        st.error("Event session is not available.")
        return

    question_set = resolve_question_set_bundle(
        session=session, session_code=config.session_code
    ).question_set
    rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(config.session_code),
    )
    submissions = repo.group_rows_by_submission(rows)
    results = build_prediction_results(submissions, active_questions(question_set))

    _render_opening(config, results)
    for index, signal in enumerate(results.questions, start=1):
        _render_question(
            signal,
            config.result_config.interpretation_for(signal.question_id),
            index,
        )


if __name__ == "__main__":
    main()
