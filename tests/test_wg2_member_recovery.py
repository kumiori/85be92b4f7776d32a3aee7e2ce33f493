from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from conference.question_sets import QuestionDefinition, QuestionRevision, QuestionSet
from conference.wg2_members import (
    approve_identity_claim,
    approve_identity_claim_with_audit,
    build_wg2_member_candidates,
    claim_directory_entries,
    create_identity_claim,
    create_recovery_request,
    issue_recovery_token,
    mask_email,
    public_claiming_enabled,
    reduce_recovery_events,
    recovery_token_fingerprint,
    recovery_token_state,
    resolve_member_route_state,
    verify_recovery_token,
)


WG2_SESSION_ID = "session-wg2"
WG2_SESSION_CODE = "un_wg2_core_2026"
WG2_TEXT_ID = "un_wg2_v1"
ROOT = Path(__file__).resolve().parents[1]


def _schema() -> QuestionSet:
    old = QuestionDefinition(
        step="role",
        field="wg2_role_lens",
        question_id="UN_WG2_ROLE_LENS",
        prompt="What is your main role or lens in WG2?",
        input_type="multi",
        options=({"value": "core_wg2_leadership", "label": "Core WG2 leadership"},),
    )
    current = QuestionDefinition(
        step="role",
        field="wg2_role_lens",
        question_id="UN_WG2_ROLE_LENS_V2",
        prompt="What is your main role or lens in WG2?",
        input_type="multi",
        options=(
            {"value": "core_group", "label": "Core WG2 group"},
            {"value": "leadership", "label": "WG2 leadership"},
        ),
        revision=QuestionRevision(
            supersedes="UN_WG2_ROLE_LENS",
            change_type="split",
            reason="Core group and leadership were previously conflated.",
            reask_if_answered=True,
            preserve_previous_response=True,
        ),
    )
    new = QuestionDefinition(
        step="new_signal",
        field="new_signal",
        question_id="UN_WG2_NEW_SIGNAL",
        prompt="One new signal?",
    )
    return QuestionSet(
        id=WG2_TEXT_ID,
        source_module=__name__,
        step_copy={},
        step_order=("role", "new_signal"),
        flow_modes={"quick": {"title": "Quick", "detail": "", "accent": "", "steps": ["role", "new_signal"]}},
        questions=(current, new),
        profile_fields=("wg2_role_lens",),
        session_fields=("new_signal",),
        deferrable_fields=(),
        fingerprint_axes=(),
        fingerprint_labels={},
        follow_up_contact_values=(),
        migration_profile_fields=(),
        version="2",
        schema_id="questionnaire_v2",
        legacy_questions=(old,),
    )


def _hash(access_key: str) -> str:
    return hashlib.sha256(access_key.encode("utf-8")).hexdigest()


def _submission(access_key: str, *, session_code=WG2_SESSION_CODE, text_id=WG2_TEXT_ID):
    return {
        "response_id": "response-v1",
        "access_key_hash": _hash(access_key),
        "submitted_at": "2026-07-01T10:00:00+00:00",
        "session_code": session_code,
        "text_id": text_id,
        "question_set_id": WG2_TEXT_ID,
        "schema_id": "questionnaire_v1",
        "alias": "Marie",
        "wg2_role_lens": ["core_wg2_leadership"],
        "profile": {"wg2_role_lens": ["core_wg2_leadership"]},
        "session": {
            "session_code": session_code,
            "text_id": text_id,
            "question_set_id": WG2_TEXT_ID,
            "schema_id": "questionnaire_v1",
        },
    }


def test_member_population_starts_from_wg2_responses_and_keeps_alignment():
    wg2_key = "0123456789ABCDEF0123456789ABCDEF"
    other_key = "FEDCBA9876543210FEDCBA9876543210"
    candidates = build_wg2_member_candidates(
        submissions=[
            _submission(wg2_key),
            _submission(other_key, session_code="other-event", text_id="other-v1"),
        ],
        players=[
            {"id": "player-wg2", "access_key": wg2_key, "nickname": "Marie", "email": "marie@example.org"},
            {"id": "player-other", "access_key": other_key, "nickname": "Other"},
            {"id": "player-without-response", "access_key": "A" * 32, "nickname": "Unrelated"},
        ],
        current_schema=_schema(),
        session_id=WG2_SESSION_ID,
    )

    assert [candidate["player_id"] for candidate in candidates] == ["player-wg2"]
    member = candidates[0]
    assert member["response_count"] == 1
    assert member["schema"] == "questionnaire_v1"
    assert member["email_status"] == "present"
    assert len(member["alignment"]["needs_refinement"]) == 1
    assert len(member["alignment"]["new_questions"]) == 1


def test_member_population_keeps_latest_append_only_bundle_per_player():
    wg2_key = "0123456789ABCDEF0123456789ABCDEF"
    previous = _submission(wg2_key)
    latest = _submission(wg2_key)
    latest["response_id"] = "response-v2"
    latest["submitted_at"] = "2026-09-05T10:00:00+00:00"
    latest["schema_id"] = "questionnaire_v2"
    latest["profile"] = {"wg2_role_lens": ["leadership"]}
    latest["session"] = {
        **latest["session"],
        "schema_id": "questionnaire_v2",
        "response_refinements": [{"question_id": "UN_WG2_ROLE_LENS_V2"}],
    }

    candidates = build_wg2_member_candidates(
        submissions=[previous, latest],
        players=[{"id": "player-wg2", "access_key": wg2_key, "nickname": "Marie"}],
        current_schema=_schema(),
        session_id=WG2_SESSION_ID,
    )

    assert len(candidates) == 1
    assert candidates[0]["response_id"] == "response-v2"
    assert candidates[0]["alignment"]["needs_refinement"] == []


def test_member_directory_includes_anonymous_wg2_participants_and_marks_them():
    entries = claim_directory_entries(
        [
            {
                "player_id": "identified-player",
                "display_name": "Marie",
                "identity_status": "identified",
            },
            {
                "player_id": "anonymous-player",
                "display_name": "Anonymous participant P02",
                "identity_status": "anonymous",
            },
        ]
    )

    assert len(entries) == 2
    assert entries[1]["identity_status"] == "anonymous"
    assert entries[0]["claimable"] is True
    assert entries[1]["claimable"] is False


def test_public_claiming_is_closed_by_default_and_follows_latest_host_event():
    assert public_claiming_enabled([]) is False
    events = [
        {
            "event_type": "public_claiming_disabled",
            "timestamp": "2026-09-05T10:10:00+00:00",
        },
        {
            "event_type": "public_claiming_enabled",
            "timestamp": "2026-09-05T10:00:00+00:00",
        },
    ]

    assert public_claiming_enabled(events) is False
    events.append(
        {
            "event_type": "public_claiming_enabled",
            "timestamp": "2026-09-05T10:20:00+00:00",
        }
    )
    assert public_claiming_enabled(events) is True


def test_admin_login_opens_recovery_surface_instead_of_member_mismatch():
    state, candidate = resolve_member_route_state(
        active_player_id="admin-player",
        player_role="admin",
        candidates=[{"player_id": "wg2-player", "display_name": "Marie"}],
    )

    assert state == "claim"
    assert candidate is None


def test_member_route_distinguishes_recovery_from_unrelated_login():
    candidates = [{"player_id": "wg2-player", "display_name": "Marie"}]

    state, candidate = resolve_member_route_state(
        active_player_id="wg2-player",
        player_role="admin",
        candidates=candidates,
        explicitly_recovered=True,
    )
    assert state == "member"
    assert candidate and candidate["player_id"] == "wg2-player"

    state, candidate = resolve_member_route_state(
        active_player_id="other-player",
        player_role="participant",
        candidates=candidates,
    )
    assert state == "not_wg2_participant"
    assert candidate is None


def test_existing_email_recovery_request_is_masked_and_contains_no_key():
    member = {
        "player_id": "player-wg2",
        "display_name": "Marie",
        "email": "marie@example.org",
        "access_key": "0123456789ABCDEF0123456789ABCDEF",
    }

    request = create_recovery_request(
        member,
        requested_at="2026-09-05T10:00:00+00:00",
        request_id="recovery-1",
    )

    assert mask_email(member["email"]) == "m••••@example.org"
    assert request["status"] == "pending"
    assert request["email_mask"] == "m••••@example.org"
    assert "access_key" not in request
    assert member["access_key"] not in str(request)


def test_missing_email_claim_stays_pending_until_host_decision():
    requested = create_identity_claim(
        player_id="player-wg2",
        proposed_email="new@example.org",
        requested_at="2026-09-05T10:00:00+00:00",
        claim_id="claim-1",
    )
    states = reduce_recovery_events(
        [{"event_type": "identity_claim_requested", "timestamp": requested["requested_at"], "metadata": requested}]
    )

    assert states["claim-1"]["status"] == "pending"
    assert states["claim-1"]["proposed_email"] == "new@example.org"


def test_revoked_claim_can_be_requested_again():
    requested = create_identity_claim(
        player_id="player-wg2",
        proposed_email="new@example.org",
        requested_at="2026-09-05T10:00:00+00:00",
        claim_id="claim-1",
    )
    states = reduce_recovery_events(
        [
            {
                "event_type": "identity_claim_requested",
                "timestamp": requested["requested_at"],
                "metadata": requested,
            },
            {
                "event_type": "recovery_workflow_revoked",
                "timestamp": "2026-09-05T10:05:00+00:00",
                "metadata": {"claim_id": "claim-1", "player_id": "player-wg2"},
            },
        ]
    )

    assert states["claim-1"]["status"] == "revoked"


class _PlayerRepo:
    def __init__(self):
        self.players = {
            "player-wg2": {
                "id": "player-wg2",
                "access_key": "0123456789ABCDEF0123456789ABCDEF",
                "nickname": "Marie",
                "email": "",
            }
        }
        self.updated = []
        self.upserted = []

    def get_player_by_id(self, player_id):
        return self.players.get(player_id)

    def update_player_metadata(self, player_id, *, email=None, **_kwargs):
        self.updated.append((player_id, email))
        self.players[player_id] = {**self.players[player_id], "email": email}
        return self.players[player_id]

    def upsert_player(self, **kwargs):
        self.upserted.append(kwargs)
        raise AssertionError("Approval must not mint or upsert another player")


def test_claim_approval_attaches_email_to_existing_player_without_minting():
    repo = _PlayerRepo()
    claim = create_identity_claim(
        player_id="player-wg2",
        proposed_email="new@example.org",
        requested_at="2026-09-05T10:00:00+00:00",
        claim_id="claim-1",
    )

    updated = approve_identity_claim(repo, claim)

    assert updated["id"] == "player-wg2"
    assert updated["access_key"] == "0123456789ABCDEF0123456789ABCDEF"
    assert updated["email"] == "new@example.org"
    assert repo.updated == [("player-wg2", "new@example.org")]
    assert repo.upserted == []


def test_claim_approval_fails_closed_when_email_was_not_persisted():
    repo = _PlayerRepo()
    repo.update_player_metadata = lambda player_id, email=None: repo.players[player_id]
    claim = create_identity_claim(
        player_id="player-wg2",
        proposed_email="new@example.org",
        requested_at="2026-09-05T10:00:00+00:00",
        claim_id="claim-1",
    )

    with pytest.raises(RuntimeError, match="email schema"):
        approve_identity_claim(repo, claim)


def test_claim_approval_rolls_back_when_audit_write_fails():
    repo = _PlayerRepo()
    claim = create_identity_claim(
        player_id="player-wg2",
        proposed_email="new@example.org",
        requested_at="2026-09-05T10:00:00+00:00",
        claim_id="claim-1",
    )

    with pytest.raises(RuntimeError, match="rolled back"):
        approve_identity_claim_with_audit(repo, claim, lambda: False)

    assert repo.players["player-wg2"]["email"] == ""
    assert repo.updated == [
        ("player-wg2", "new@example.org"),
        ("player-wg2", ""),
    ]


def test_recovery_token_resolves_existing_player_and_is_session_scoped():
    issued_at = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    token = issue_recovery_token(
        player_id="player-wg2",
        session_id=WG2_SESSION_ID,
        secret="test-secret",
        issued_at=issued_at,
        ttl_seconds=3600,
        nonce="fixed-nonce",
    )

    recovered = verify_recovery_token(
        token,
        secret="test-secret",
        expected_session_id=WG2_SESSION_ID,
        now=datetime(2026, 9, 5, 10, 30, tzinfo=timezone.utc),
    )

    assert recovered["player_id"] == "player-wg2"
    assert recovered["session_id"] == WG2_SESSION_ID
    fingerprint = recovery_token_fingerprint(token)
    assert recovery_token_state(
        [
            {
                "event_type": "recovery_link_issued",
                "metadata": {"token_hash": fingerprint},
            }
        ],
        token,
    ) == "issued"
    assert recovery_token_state(
        [
            {
                "event_type": "recovery_link_issued",
                "metadata": {"token_hash": fingerprint},
            },
            {
                "event_type": "recovery_link_redeemed",
                "metadata": {"token_hash": fingerprint},
            },
        ],
        token,
    ) == "redeemed"
    with pytest.raises(ValueError, match="session"):
        verify_recovery_token(
            token,
            secret="test-secret",
            expected_session_id="another-session",
            now=datetime(2026, 9, 5, 10, 30, tzinfo=timezone.utc),
        )


def test_member_and_host_routes_expose_refinement_and_protected_recovery_actions():
    member_source = (ROOT / "pages" / "32_UN_WG2_Member.py").read_text()
    host_source = (ROOT / "pages" / "27_UN_WG2_Host.py").read_text()
    app_source = (ROOT / "app.py").read_text()

    assert 'url_path="un-wg2-member"' in app_source
    assert "We refined this question" in member_source
    assert "Previously we asked" in member_source
    assert "Your previous answer" in member_source
    assert "Reason for change" in member_source
    assert "build_refinement_bundle" in member_source
    assert "approve_identity_claim" in host_source
    assert "Prepare one-time recovery link" in host_source
    assert "Revoke and allow retry" in host_source
    assert "Allow public claiming" in host_source
    assert "Create WG2 test session" in host_source
    assert "Open WG2 test questionnaire" in host_source
    assert "public_claiming_enabled(events)" in member_source
    assert '"/un-wg2-icebreaker?test=1"' in host_source
    assert "Open WG2 Host approval" in member_source
    assert "_render_member_recovery_support(" in host_source
    assert "_render_credential_support(" not in host_source.split("with tabs[1]:", 1)[1]


def test_expired_or_tampered_recovery_token_is_rejected():
    token = issue_recovery_token(
        player_id="player-wg2",
        session_id=WG2_SESSION_ID,
        secret="test-secret",
        issued_at=datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
        ttl_seconds=60,
        nonce="fixed-nonce",
    )

    with pytest.raises(ValueError, match="expired"):
        verify_recovery_token(
            token,
            secret="test-secret",
            expected_session_id=WG2_SESSION_ID,
            now=datetime(2026, 9, 5, 10, 2, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="signature"):
        verify_recovery_token(
            token + "x",
            secret="test-secret",
            expected_session_id=WG2_SESSION_ID,
            now=datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="unavailable"):
        verify_recovery_token(
            token,
            secret="",
            expected_session_id=WG2_SESSION_ID,
            now=datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
        )
