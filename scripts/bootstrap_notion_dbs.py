#!/usr/bin/env python3
import os
import sys
import json
import datetime as dt
from notion_client import Client


# -------------------------
# Helpers
# -------------------------
def iso_now():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def assert_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var {name}")
    return v


def db_update(client: Client, db_id: str, properties: dict):
    return client.databases.update(database_id=db_id, properties=properties)


def db_retrieve(client: Client, db_id: str):
    return client.databases.retrieve(database_id=db_id)


def ensure_page_in_db_by_title(
    client: Client, db_id: str, title_prop: str, title_value: str, extra_props: dict
):
    # Query by title equals
    res = client.databases.query(
        database_id=db_id,
        filter={"property": title_prop, "title": {"equals": title_value}},
    )
    if res.get("results"):
        return res["results"][0]["id"], False

    created = client.pages.create(
        parent={"database_id": db_id},
        properties={
            title_prop: {"title": [{"type": "text", "text": {"content": title_value}}]},
            **extra_props,
        },
    )
    return created["id"], True


def print_db_properties(client: Client, db_id: str, label: str):
    db = db_retrieve(client, db_id)
    props = db.get("properties", {})
    print(f"\n[{label}] properties:")
    for k, v in props.items():
        print(f"  - {k}: {v.get('type')}")


# -------------------------
# Main
# -------------------------
def main():
    token = assert_env("NOTION_TOKEN")

    # Database IDs (use your exports)
    ICE_PLAYERS_DB_ID = assert_env("ICE_PLAYERS_DB_ID")
    ICE_SESSIONS_DB_ID = assert_env("ICE_SESSIONS_DB_ID")
    ICE_STATEMENTS_DB_ID = assert_env("ICE_STATEMENTS_DB_ID")
    ICE_RESPONSES_DB_ID = assert_env("ICE_RESPONSES_DB_ID")
    ICE_QUESTIONS_DB_ID = assert_env("ICE_QUESTIONS_DB_ID")
    ICE_VOTES_DB_ID = assert_env("ICE_VOTES_DB_ID")
    ICE_DECISIONS_DB_ID = assert_env("ICE_DECISIONS_DB_ID")

    client = Client(auth=token)

    # --- 1) Players schema additions
    db_update(
        client,
        ICE_PLAYERS_DB_ID,
        properties={
            "access_key": {"rich_text": {}},
            "emoji": {"rich_text": {}},
            "emoji_suffix_4": {"rich_text": {}},
            "emoji_suffix_6": {"rich_text": {}},
            "phrase": {"rich_text": {}},
            "status": {
                "select": {
                    "options": [
                        {"name": "active", "color": "green"},
                        {"name": "revoked", "color": "red"},
                    ]
                }
            },
        },
    )

    # --- 2) Sessions schema
    # Keep the existing title property name (likely "Title" or "Name"). We will not rename it.
    db_update(
        client,
        ICE_SESSIONS_DB_ID,
        properties={
            "active": {"checkbox": {}},
            "start": {"date": {}},
            "end": {"date": {}},
            "created_at": {"date": {}},
            "notes": {"rich_text": {}},
        },
    )

    # --- 3) Statements schema
    db_update(
        client,
        ICE_STATEMENTS_DB_ID,
        properties={
            "theme": {
                "select": {
                    "options": [
                        {"name": "irreversibility", "color": "blue"},
                        {"name": "antarctica-commons", "color": "yellow"},
                        {"name": "agency", "color": "green"},
                        {"name": "emotion-rationality", "color": "purple"},
                        {"name": "science-dialogue", "color": "gray"},
                        {"name": "other", "color": "default"},
                    ]
                }
            },
            "active": {"checkbox": {}},
            "order": {"number": {"format": "number"}},
            # relation added below
        },
    )

    # --- 4) Responses schema
    db_update(
        client,
        ICE_RESPONSES_DB_ID,
        properties={
            "value": {"number": {"format": "number"}},
            "level_label": {
                "select": {
                    "options": [
                        {"name": "dissonance", "color": "red"},
                        {"name": "low", "color": "orange"},
                        {"name": "neutral", "color": "gray"},
                        {"name": "high", "color": "blue"},
                        {"name": "full", "color": "green"},
                    ]
                }
            },
            "note": {"rich_text": {}},
            "created_at": {"date": {}},
            # relations added below
        },
    )

    # --- 5) Questions schema
    db_update(
        client,
        ICE_QUESTIONS_DB_ID,
        properties={
            "domain": {
                "select": {
                    "options": [
                        {"name": "ice", "color": "blue"},
                        {"name": "mechanics", "color": "purple"},
                        {"name": "policy", "color": "yellow"},
                        {"name": "media", "color": "pink"},
                        {"name": "ethics", "color": "red"},
                        {"name": "other", "color": "gray"},
                    ]
                }
            },
            "status": {
                "select": {
                    "options": [
                        {"name": "pending", "color": "gray"},
                        {"name": "approved", "color": "green"},
                        {"name": "rewrite", "color": "orange"},
                        {"name": "parked", "color": "red"},
                    ]
                }
            },
            "approve_count": {"number": {"format": "number"}},
            "rewrite_count": {"number": {"format": "number"}},
            "park_count": {"number": {"format": "number"}},
            "created_at": {"date": {}},
            "last_updated": {"date": {}},
            # relations added below
        },
    )

    # --- 6) ModerationVotes schema
    db_update(
        client,
        ICE_VOTES_DB_ID,
        properties={
            "vote": {
                "select": {
                    "options": [
                        {"name": "approve", "color": "green"},
                        {"name": "rewrite", "color": "orange"},
                        {"name": "park", "color": "red"},
                    ]
                }
            },
            "created_at": {"date": {}},
            # relations added below
        },
    )

    # --- 7) Decisions schema
    db_update(
        client,
        ICE_DECISIONS_DB_ID,
        properties={
            "type": {
                "select": {
                    "options": [
                        {"name": "description_status", "color": "blue"},
                        {"name": "journey_A", "color": "gray"},
                        {"name": "journey_B", "color": "gray"},
                        {"name": "structure_choice", "color": "purple"},
                    ]
                }
            },
            "payload": {"rich_text": {}},
            "created_at": {"date": {}},
            # relations added below
        },
    )

    # --- 8) Relations (official Notion API syntax)
    # Note: relations have to be created on both sides if you want both-direction UX;
    # Notion will create a paired property if you include "synced_property_name".
    #
    # We'll create one-way relations for v0 (simpler). You can later add the reverse in UI.
    db_update(
        client,
        ICE_STATEMENTS_DB_ID,
        properties={
            "session": {
                "relation": {
                    "database_id": ICE_SESSIONS_DB_ID,
                    "dual_property": {"synced_property_name": "statements"},
                }
            }
        },
    )
    db_update(
        client,
        ICE_RESPONSES_DB_ID,
        properties={
            "session": {
                "relation": {
                    "database_id": ICE_SESSIONS_DB_ID,
                    "dual_property": {"synced_property_name": "responses"},
                }
            },
            "player": {
                "relation": {
                    "database_id": ICE_PLAYERS_DB_ID,
                    "dual_property": {"synced_property_name": "responses"},
                }
            },
            "statement": {
                "relation": {
                    "database_id": ICE_STATEMENTS_DB_ID,
                    "dual_property": {"synced_property_name": "responses"},
                }
            },
        },
    )
    db_update(
        client,
        ICE_QUESTIONS_DB_ID,
        properties={
            "session": {
                "relation": {
                    "database_id": ICE_SESSIONS_DB_ID,
                    "dual_property": {"synced_property_name": "questions"},
                }
            },
            "submitted_by": {
                "relation": {
                    "database_id": ICE_PLAYERS_DB_ID,
                    "dual_property": {"synced_property_name": "questions_submitted"},
                }
            },
        },
    )
    db_update(
        client,
        ICE_VOTES_DB_ID,
        properties={
            "session": {
                "relation": {
                    "database_id": ICE_SESSIONS_DB_ID,
                    "dual_property": {"synced_property_name": "moderation_votes"},
                }
            },
            "question": {
                "relation": {
                    "database_id": ICE_QUESTIONS_DB_ID,
                    "dual_property": {"synced_property_name": "moderation_votes"},
                }
            },
            "voter": {
                "relation": {
                    "database_id": ICE_PLAYERS_DB_ID,
                    "dual_property": {"synced_property_name": "moderation_votes"},
                }
            },
        },
    )
    db_update(
        client,
        ICE_DECISIONS_DB_ID,
        properties={
            "session": {
                "relation": {
                    "database_id": ICE_SESSIONS_DB_ID,
                    "dual_property": {"synced_property_name": "decisions"},
                }
            },
            "player": {
                "relation": {
                    "database_id": ICE_PLAYERS_DB_ID,
                    "dual_property": {"synced_property_name": "decisions"},
                }
            },
        },
    )
    # --- 9) Seed GLOBAL-SESSION
    # Need the actual title property name in ice_Sessions ("Title" vs "Name")
    sessions_db = db_retrieve(client, ICE_SESSIONS_DB_ID)
    title_prop = None
    for prop_name, prop in sessions_db["properties"].items():
        if prop["type"] == "title":
            title_prop = prop_name
            break
    if not title_prop:
        raise RuntimeError("Could not find title property in ice_Sessions")

    session_id, created = ensure_page_in_db_by_title(
        client,
        ICE_SESSIONS_DB_ID,
        title_prop,
        "GLOBAL-SESSION",
        extra_props={
            "active": {"checkbox": True},
            "created_at": {"date": {"start": iso_now()}},
            "notes": {"rich_text": [{"type": "text", "text": {"content": "v0 seed"}}]},
        },
    )
    print(f"\nGLOBAL-SESSION: {'created' if created else 'exists'} ({session_id})")

    # --- 10) Print property lists as verification
    print_db_properties(client, ICE_PLAYERS_DB_ID, "ice_Players")
    print_db_properties(client, ICE_SESSIONS_DB_ID, "ice_Sessions")
    print_db_properties(client, ICE_STATEMENTS_DB_ID, "ice_Statements")
    print_db_properties(client, ICE_RESPONSES_DB_ID, "ice_Responses")
    print_db_properties(client, ICE_QUESTIONS_DB_ID, "ice_Questions")
    print_db_properties(client, ICE_VOTES_DB_ID, "ice_ModerationVotes")
    print_db_properties(client, ICE_DECISIONS_DB_ID, "ice_Decisions")

    print("\nDone. Refresh Notion UI; you should see new properties and relations.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR]", e)
        sys.exit(1)
