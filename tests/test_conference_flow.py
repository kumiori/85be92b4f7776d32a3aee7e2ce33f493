from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.flow import (
    active_question_steps,
    build_payload_view,
    build_session_payload,
    pending_reflection_fields,
    profile_completion_gaps,
    should_collect_contact,
    step_is_complete,
)
from conference.question_sets.un_wg2_v1 import QUESTION_SET as UN_WG2_V1_QUESTION_SET


def test_build_session_payload_emits_schema_v2_and_filters_values():
    payload = build_session_payload(
        {
            "mode": "standard",
            "role": ["theory", "unknown", "theory"],
            "career_stage": "phd",
            "scientific_home_country": " Serbia ",
            "scientific_home_city": " Belgrade ",
            "scientific_home_institution": " Petnica ",
            "scale": "hpc",
            "collaboration_style": "bridge_builder",
            "assets": ["computation", "software", "software", "bad"],
            "motivations": ["methods", "collaboration", "bad", "methods"],
            "obstacle": ["data", "coordination", "bad"],
            "challenge": "benchmark",
            "follow_up_interest": "yes",
            "complexity_fingerprint": {"theory": 5, "data": 2, "experiments": 0, "mechanisms": 7},
            "open_question": "  How do transitions emerge? ",
            "boiler_room_contribution": "  Poster draft: https://example.org/poster  ",
            "question_flags": {
                "COMPLEXITY_ROLE": {
                    "flags": [
                        "interesting_question",
                        "useful_for_coordination",
                        "misleading",
                        "bad",
                        "misleading",
                    ],
                    "note": "  Missing hybrid options  ",
                },
                "": {"flags": ["unclear"]},
            },
            "alias": "  Alias  ",
            "identity": "  ",
            "contact": "  site.example  ",
            "identity_reveal_targets": ["player:abc", "player:abc", "player:def"],
        }
    )
    assert payload["schema_version"] == "2"
    assert payload["profile"]["assets"] == ["computation", "software"]
    assert payload["profile"]["role"] == ["theory"]
    assert payload["profile"]["scientific_home"]["country"] == "Serbia"
    assert payload["profile"]["scientific_home"]["city"] == "Belgrade"
    assert payload["profile"]["scientific_home"]["institution"] == "Petnica"
    assert payload["profile"]["complexity_fingerprint"]["mechanisms"] == 5
    assert payload["session"]["depth"] == "standard"
    assert payload["session"]["motivations"] == ["methods", "collaboration"]
    assert payload["session"]["obstacle"] == ["data", "coordination"]
    assert payload["session"]["challenge"] == "benchmark"
    assert payload["session"]["follow_up_interest"] == "yes"
    assert payload["session"]["open_question"] == "How do transitions emerge?"
    assert (
        payload["session"]["boiler_room_contribution"]
        == "Poster draft: https://example.org/poster"
    )
    assert payload["session"]["question_flags"] == {
        "COMPLEXITY_ROLE": {
            "flags": [
                "interesting_question",
                "useful_for_coordination",
                "misleading",
            ],
            "note": "Missing hybrid options",
        }
    }
    assert payload["session"]["identity_reveal_targets"] == ["player:abc", "player:def"]

    view = build_payload_view(
        {
            "mode": "standard",
            "role": ["theory", "unknown", "theory"],
            "career_stage": "phd",
            "scientific_home_country": " Serbia ",
            "scientific_home_city": " Belgrade ",
            "scientific_home_institution": " Petnica ",
            "scale": "hpc",
            "collaboration_style": "bridge_builder",
            "assets": ["computation", "software", "software", "bad"],
            "motivations": ["methods", "collaboration", "bad", "methods"],
            "obstacle": ["data", "coordination", "bad"],
            "challenge": "benchmark",
            "follow_up_interest": "yes",
            "complexity_fingerprint": {"theory": 5, "data": 2, "experiments": 0, "mechanisms": 7},
            "open_question": "  How do transitions emerge? ",
            "boiler_room_contribution": "  Poster draft: https://example.org/poster  ",
            "question_flags": {
                "COMPLEXITY_ROLE": {
                    "flags": ["misleading"],
                    "note": "Missing hybrid options",
                }
            },
            "alias": "  Alias  ",
            "identity": "  ",
            "contact": "  site.example  ",
            "identity_reveal_targets": ["player:abc", "player:abc", "player:def"],
        }
    )
    assert view["mode"] == "standard"
    assert view["role"] == ["theory"]
    assert view["follow_up_interest"] == "yes"
    assert view["boiler_room_contribution"] == "Poster draft: https://example.org/poster"
    assert view["question_flags"] == {
        "COMPLEXITY_ROLE": {
            "flags": ["misleading"],
            "note": "Missing hybrid options",
        }
    }
    assert view["contact"] == "site.example"
    assert view["contact_label"] == "Alias"


def test_build_session_payload_supports_funding_and_none():
    payload = build_session_payload(
        {
            "mode": "quick",
            "role": ["models"],
            "assets": ["data"],
            "motivations": ["application"],
            "obstacle": ["funding"],
            "challenge": "none",
            "follow_up_interest": "no",
        }
    )
    assert payload["session"]["obstacle"] == ["funding"]
    assert payload["session"]["challenge"] == "none"


def test_step_completion_for_required_and_deferrable_fields():
    draft = {
        "mode": "standard",
        "role": ["theory"],
        "scientific_home_country": "",
        "scientific_home_city": "",
        "scientific_home_institution": "",
        "scale": "hpc",
        "collaboration_style": "small_team",
        "assets": ["software"],
        "motivations": ["methods"],
        "obstacle": ["data"],
        "challenge": "benchmark",
        "follow_up_interest": "yes",
        "complexity_fingerprint": {"theory": 0, "data": 0, "experiments": 0, "mechanisms": 0},
        "open_question": "",
        "deferred_fields": ["complexity_fingerprint", "open_question"],
    }
    assert step_is_complete("role", draft) is True
    assert step_is_complete("scientific_home", draft) is True
    assert step_is_complete("complexity_fingerprint", draft) is True
    assert step_is_complete("open_question", draft) is True
    draft["role"] = []
    assert step_is_complete("role", draft) is False


def test_mode_controls_active_steps_and_contact_gate():
    quick = {"mode": "quick", "follow_up_interest": "no"}
    deep = {"mode": "deep", "follow_up_interest": "maybe"}
    assert active_question_steps(quick) == [
        "role",
        "assets",
        "motivations",
        "obstacle",
        "challenge",
        "follow_up_interest",
    ]
    assert "career_stage" in active_question_steps(deep)
    assert "complexity_fingerprint" in active_question_steps(deep)
    assert should_collect_contact(quick) is False
    assert should_collect_contact(deep) is True


def test_wg2_collects_optional_contact_without_follow_up_question():
    assert should_collect_contact({}, question_set=UN_WG2_V1_QUESTION_SET) is True


def test_wg2_geography_context_preserves_lookup_provenance():
    draft = {
        "mode": "quick",
        "wg2_main_location": {
            "country_region": "France",
            "institution_location": "UNESCO Paris",
            "coordinates_consent": "lookup",
            "coordinates": "48.849000, 2.306000",
            "geocode_query": "UNESCO Paris, France",
            "geocode_label": "UNESCO, Paris, Ile-de-France, France",
            "geocode_source": "opencage",
        },
    }

    payload = build_session_payload(draft, question_set=UN_WG2_V1_QUESTION_SET)
    location = payload["profile"]["wg2_main_location"]

    assert location["coordinates_consent"] == "lookup"
    assert location["coordinates"] == "48.849000, 2.306000"
    assert location["geocode_query"] == "UNESCO Paris, France"
    assert location["geocode_source"] == "opencage"


def test_pending_reflections_and_profile_gaps_are_detected():
    draft = {
        "mode": "standard",
        "scientific_home_country": "",
        "assets": [],
        "collaboration_style": "",
        "complexity_fingerprint": {"theory": 0, "data": 0, "experiments": 0, "mechanisms": 0},
        "deferred_fields": ["complexity_fingerprint", "open_question"],
        "open_question": "",
    }
    assert pending_reflection_fields(draft) == ["complexity_fingerprint", "open_question"]
    assert profile_completion_gaps(draft) == [
        "scientific_home_country",
        "assets",
        "collaboration_style",
        "complexity_fingerprint",
    ]
