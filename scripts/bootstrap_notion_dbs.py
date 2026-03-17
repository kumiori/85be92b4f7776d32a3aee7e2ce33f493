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
    try:
        data_sources = getattr(client, "data_sources", None)
        ds_update = getattr(data_sources, "update", None) if data_sources else None
        if callable(ds_update):
            ds_id = resolve_data_source_id(client, db_id)
            return ds_update(data_source_id=ds_id, properties=properties)
        return client.databases.update(database_id=db_id, properties=properties)
    except Exception as exc:
        prop_names = ", ".join(sorted(properties.keys()))
        raise RuntimeError(
            f"Notion schema update failed for db_id={db_id}. "
            f"Properties=[{prop_names}]. Cause: {exc}"
        ) from exc


def db_retrieve(client: Client, db_id: str):
    try:
        data_sources = getattr(client, "data_sources", None)
        ds_retrieve = getattr(data_sources, "retrieve", None) if data_sources else None
        if callable(ds_retrieve):
            ds_id = resolve_data_source_id(client, db_id)
            return ds_retrieve(data_source_id=ds_id)
        return client.databases.retrieve(database_id=db_id)
    except Exception as exc:
        raise RuntimeError(
            f"Notion retrieve failed for db_id={db_id}. Cause: {exc}"
        ) from exc


def resolve_data_source_id(client: Client, db_or_ds_id: str) -> str:
    data_sources = getattr(client, "data_sources", None)
    ds_retrieve = getattr(data_sources, "retrieve", None) if data_sources else None
    if callable(ds_retrieve):
        try:
            ds_retrieve(data_source_id=db_or_ds_id)
            return db_or_ds_id
        except Exception:
            pass

    db = client.databases.retrieve(database_id=db_or_ds_id)
    data_sources_list = db.get("data_sources", []) if isinstance(db, dict) else []
    if data_sources_list and isinstance(data_sources_list[0], dict):
        ds_id = data_sources_list[0].get("id")
        if ds_id:
            return str(ds_id)
    return db_or_ds_id


def db_query(client: Client, db_id: str, **kwargs):
    try:
        data_sources = getattr(client, "data_sources", None)
        ds_query = getattr(data_sources, "query", None) if data_sources else None
        if callable(ds_query):
            ds_id = resolve_data_source_id(client, db_id)
            return ds_query(data_source_id=ds_id, **kwargs)
        return client.databases.query(database_id=db_id, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"Notion query failed for db_id={db_id}. kwargs={json.dumps(kwargs)}. Cause: {exc}"
        ) from exc


def parent_for_collection(client: Client, db_id: str) -> dict:
    data_sources = getattr(client, "data_sources", None)
    if callable(getattr(data_sources, "query", None)):
        return {"data_source_id": resolve_data_source_id(client, db_id)}
    return {"database_id": db_id}


def relation_spec(client: Client, target_db_id: str, synced_property_name: str) -> dict:
    data_sources = getattr(client, "data_sources", None)
    if callable(getattr(data_sources, "update", None)):
        return {
            "relation": {
                "data_source_id": resolve_data_source_id(client, target_db_id),
                "dual_property": {"synced_property_name": synced_property_name},
            }
        }
    return {
        "relation": {
            "database_id": target_db_id,
            "dual_property": {"synced_property_name": synced_property_name},
        }
    }


def ensure_page_in_db_by_title(
    client: Client, db_id: str, title_prop: str, title_value: str, extra_props: dict
):
    # Query by title equals
    res = db_query(
        client,
        db_id,
        filter={"property": title_prop, "title": {"equals": title_value}},
    )
    if res.get("results"):
        return res["results"][0]["id"], False

    created = client.pages.create(
        parent=parent_for_collection(client, db_id),
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
    ICE_EVENTS_DB_ID = os.getenv("ICE_EVENTS_DB_ID", "").strip()

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
            "session_name": {"rich_text": {}},
            "session_title": {"rich_text": {}},
            "session_order": {"number": {"format": "number"}},
            "session_description": {"rich_text": {}},
            "session_visualisation": {"rich_text": {}},
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
            "question_id": {"rich_text": {}},
            "response_value": {"rich_text": {}},
            "timestamp": {"date": {}},
            "access_key": {"rich_text": {}},
            "value": {"rich_text": {}},
            "value_label": {"rich_text": {}},
            "score": {"number": {"format": "number"}},
            "item_id": {"rich_text": {}},
            "depth": {"number": {"format": "number"}},
            "page_index": {"number": {"format": "number"}},
            "submitted_at": {"date": {}},
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
            "question_type": {
                "select": {
                    "options": [
                        {"name": "single", "color": "blue"},
                        {"name": "multi", "color": "purple"},
                        {"name": "text", "color": "green"},
                        {"name": "signal", "color": "orange"},
                        {"name": "other", "color": "gray"},
                    ]
                }
            },
            "optional_text": {"rich_text": {}},
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

    # --- 8b) Events schema (optional)
    # --- 8b) Events schema
    if ICE_EVENTS_DB_ID:
        db_update(
            client,
            ICE_EVENTS_DB_ID,
            properties={
                "timestamp": {"date": {}},
                "event_type": {
                    "select": {
                        "options": [
                            {"name": "login_success", "color": "green"},
                            {"name": "login_failure", "color": "red"},
                            {"name": "mint_key", "color": "blue"},
                            {"name": "signal_submit", "color": "purple"},
                            {"name": "question_submit", "color": "orange"},
                            {"name": "enter_lobby", "color": "yellow"},
                            {"name": "claim_coorganiser_success", "color": "green"},
                            {"name": "claim_coorganiser_failure", "color": "red"},
                            {"name": "session_switched", "color": "blue"},
                            {"name": "overview_loaded", "color": "gray"},
                            {"name": "page_view", "color": "default"},
                            {"name": "logout", "color": "brown"},
                            {"name": "response_save_error", "color": "red"},
                        ]
                    }
                },
                "item_id": {"rich_text": {}},
                "page": {"rich_text": {}},
                "value_label": {"rich_text": {}},
                "metadata_json": {"rich_text": {}},
                "device_id": {"rich_text": {}},
                "status": {
                    "select": {
                        "options": [
                            {"name": "ok", "color": "green"},
                            {"name": "warning", "color": "yellow"},
                            {"name": "error", "color": "red"},
                        ]
                    }
                },
            },
        )
    # --- 9) Relations (official Notion API syntax)
    # Note: relations have to be created on both sides if you want both-direction UX;
    # Notion will create a paired property if you include "synced_property_name".
    #
    # We'll create one-way relations for v0 (simpler). You can later add the reverse in UI.
    db_update(
        client,
        ICE_STATEMENTS_DB_ID,
        properties={"session": relation_spec(client, ICE_SESSIONS_DB_ID, "statements")},
    )
    db_update(
        client,
        ICE_RESPONSES_DB_ID,
        properties={
            "session": relation_spec(client, ICE_SESSIONS_DB_ID, "responses"),
            "player": relation_spec(client, ICE_PLAYERS_DB_ID, "responses"),
            "statement": relation_spec(client, ICE_STATEMENTS_DB_ID, "responses"),
        },
    )
    db_update(
        client,
        ICE_QUESTIONS_DB_ID,
        properties={
            "session": relation_spec(client, ICE_SESSIONS_DB_ID, "questions"),
            "submitted_by": relation_spec(
                client, ICE_PLAYERS_DB_ID, "questions_submitted"
            ),
        },
    )
    db_update(
        client,
        ICE_VOTES_DB_ID,
        properties={
            "session": relation_spec(client, ICE_SESSIONS_DB_ID, "moderation_votes"),
            "question": relation_spec(client, ICE_QUESTIONS_DB_ID, "moderation_votes"),
            "voter": relation_spec(client, ICE_PLAYERS_DB_ID, "moderation_votes"),
        },
    )
    db_update(
        client,
        ICE_DECISIONS_DB_ID,
        properties={
            "session": relation_spec(client, ICE_SESSIONS_DB_ID, "decisions"),
            "player": relation_spec(client, ICE_PLAYERS_DB_ID, "decisions"),
        },
    )
    if ICE_EVENTS_DB_ID:
        db_update(
            client,
            ICE_EVENTS_DB_ID,
            properties={
                "session": relation_spec(client, ICE_SESSIONS_DB_ID, "events"),
                "player": relation_spec(client, ICE_PLAYERS_DB_ID, "events"),
            },
        )
    # --- 10) Seed GLOBAL-SESSION
    # Need the actual title property name in ice_Sessions ("Title" vs "Name")
    sessions_db = db_retrieve(client, ICE_SESSIONS_DB_ID)
    title_prop = None
    for prop_name, prop in sessions_db.get("properties", {}).items():
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
            "session_name": {
                "rich_text": [{"type": "text", "text": {"content": "Global entry"}}]
            },
            "session_title": {
                "rich_text": [{"type": "text", "text": {"content": "Entry Signal"}}]
            },
            "session_order": {"number": 0},
            "session_description": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "First collective signal before entering the lobby."
                        },
                    }
                ]
            },
            "session_visualisation": {
                "rich_text": [{"type": "text", "text": {"content": "globe_map"}}]
            },
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
    if ICE_EVENTS_DB_ID:
        print_db_properties(client, ICE_EVENTS_DB_ID, "ice_Events")
    else:
        print("\n[ice_Events] skipped: ICE_EVENTS_DB_ID is not set.")

    print("\nDone. Refresh Notion UI; you should see new properties and relations.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR]", e)
        sys.exit(1)
