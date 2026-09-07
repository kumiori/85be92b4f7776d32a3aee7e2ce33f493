from __future__ import annotations

import pytest
from pathlib import Path

from conference.wg2_funding_mixer import (
    INTERACTION_ID,
    aggregate_allocations,
    allocation_payload,
    backup_document,
    backup_json,
    constrain_allocation,
    default_allocation,
    rebalance_allocation,
    validate_allocation,
)


def _full_allocation() -> dict[str, int]:
    return {
        "people": 20,
        "knowledge": 20,
        "interaction": 15,
        "infrastructure": 15,
        "deployment": 15,
        "contingency": 10,
        "other": 5,
    }

def _row(actor: str, revision: int, allocation: dict[str, int]) -> dict:
    return {
        "player_id": actor,
        "timestamp": f"2026-08-31T10:00:0{revision}+00:00",
        "value_json": allocation_payload(
            allocation,
            session_code="wg2-meeting-3",
            revision=revision,
            participant_hash=actor,
        ),
    }


def test_rebalance_keeps_exact_total_and_requested_channel() -> None:
    allocation = rebalance_allocation(_full_allocation(), "people", 47)

    assert allocation["people"] == 47
    assert sum(allocation.values()) == 100
    assert set(allocation) == set(default_allocation())


def test_rebalance_can_recover_from_all_tokens_in_one_other_channel() -> None:
    allocation = {
        "people": 100,
        "knowledge": 0,
        "interaction": 0,
        "infrastructure": 0,
        "deployment": 0,
        "contingency": 0,
        "other": 0,
    }

    balanced = rebalance_allocation(allocation, "knowledge", 25)

    assert balanced["knowledge"] == 25
    assert balanced["people"] == 75
    assert sum(balanced.values()) == 100


def test_payload_is_explicitly_scoped_and_revisioned() -> None:
    payload = allocation_payload(
        _full_allocation(),
        session_code="wg2-meeting-3",
        revision=2,
        participant_hash="anonymous-hash",
        phase="after_discussion",
    )

    assert payload["interaction"] == INTERACTION_ID
    assert payload["session_code"] == "wg2-meeting-3"
    assert payload["response_scope"] == "event_session"
    assert payload["revision"] == 2
    assert payload["phase"] == "after_discussion"


def test_debug_payload_is_explicitly_classified_and_isolated() -> None:
    payload = allocation_payload(
        _full_allocation(),
        session_code="un_wg2_debug_2026",
        revision=1,
        participant_hash="debug-participant",
        test_mode=True,
    )

    assert payload["response_scope"] == "debug_session"
    assert payload["test_mode"] is True
    assert payload["data_classification"] == "debug"


def test_invalid_total_is_rejected() -> None:
    allocation = _full_allocation() | {"people": 21}
    with pytest.raises(ValueError, match="exactly 100"):
        validate_allocation(allocation)


def test_aggregate_uses_latest_revision_per_anonymous_participant() -> None:
    first = _full_allocation()
    revised = rebalance_allocation(first, "people", 40)
    other = rebalance_allocation(first, "people", 10)

    aggregate = aggregate_allocations(
        [_row("actor-a", 1, first), _row("actor-a", 2, revised), _row("actor-b", 1, other)]
    )

    assert aggregate["submission_count"] == 2
    assert aggregate["revision_count"] == 3
    assert aggregate["channels"]["people"] == {"median": 25.0, "min": 10.0, "max": 40.0}
    assert len(aggregate["traces"]) == 2


def test_partial_allocation_reports_truth_and_contracts_only_on_overflow() -> None:
    partial = default_allocation()
    partial["people"] = 40
    partial["knowledge"] = 30

    still_partial = constrain_allocation(partial, "interaction", 20)
    constrained = constrain_allocation(still_partial, "other", 30)

    assert sum(still_partial.values()) == 90
    assert still_partial["interaction"] == 20
    assert sum(constrained.values()) == 100
    assert constrained["other"] == 30


def test_other_text_is_stored_only_when_other_receives_tokens() -> None:
    with_other = allocation_payload(
        _full_allocation(),
        session_code="wg2-meeting-3",
        revision=1,
        participant_hash="actor",
        other_text="Rapid response fund",
    )
    without_other = allocation_payload(
        _full_allocation() | {"other": 0, "people": 25},
        session_code="wg2-meeting-3",
        revision=1,
        participant_hash="actor",
        other_text="Should not persist",
    )

    assert with_other["other_text"] == "Rapid response fund"
    assert "other_text" not in without_other


def test_route_uses_philoui_equaliser_not_native_streamlit_slider() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "pages/29_WG2_Funding_Mixer.py"
    ).read_text()

    assert "from philoui.survey import CustomStreamlitSurvey" in source
    assert "survey.equaliser(" in source
    assert "st.slider(" not in source


def test_confirmation_does_not_display_the_access_key_and_confetti_is_page_level() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "pages/29_WG2_Funding_Mixer.py"
    ).read_text()

    assert "Allocation committed · revision {revision} · key" not in source
    assert 'class="wg2-confetti"' in source
    assert "position:fixed" in source
    assert "components.html(" not in source


def test_renormalisation_sets_a_visible_toast() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "pages/29_WG2_Funding_Mixer.py"
    ).read_text()

    assert 'st.session_state["wg2_mixer_v2_renormalised"] = True' in source
    assert 'st.toast("Renormalised to 100 tokens' in source


def test_backup_is_portable_and_does_not_expose_identity_linking_fields() -> None:
    payload = allocation_payload(
        _full_allocation(),
        session_code="wg2-meeting-3",
        revision=3,
        participant_hash="must-not-leak",
        other_text="Rapid response fund",
        submitted_at="2026-09-02T12:00:00+00:00",
    )

    backup = backup_document(payload)
    serialized = backup_json(payload)

    assert backup["schema"] == "wg2-funding-mix-backup/v1"
    assert backup["session_code"] == "wg2-meeting-3"
    assert backup["revision"] == 3
    assert backup["total"] == 100
    assert backup["allocation"] == _full_allocation()
    assert backup["other_text"] == "Rapid response fund"
    assert "participant_hash" not in backup
    assert "must-not-leak" not in serialized


def test_dedicated_results_route_is_registered() -> None:
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text()
    results_source = (root / "pages/31_WG2_Funding_Mixer_Results.py").read_text()

    assert 'url_path="wg2-funding-mixer-results"' in app_source
    assert "aggregate_allocations(rows)" in results_source
    assert "run_every=5" in results_source
