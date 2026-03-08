#!/usr/bin/env python3
import os
import sys
from notion_client import Client


def assert_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var {name}")
    return v


def main():
    token = assert_env("NOTION_TOKEN")
    ICE_RESPONSES_DB_ID = assert_env("ICE_RESPONSES_DB_ID")
    ICE_QUESTIONS_DB_ID = assert_env("ICE_QUESTIONS_DB_ID")

    client = Client(auth=token)

    # Safe additive migration:
    # - keep existing legacy fields
    # - add new generic interaction fields
    # - do not delete anything
    props = {
        # generic question identifier, if relation is not enough
        "item_id": {"rich_text": {}},
        # JSON payload for any answer type
        "value_json": {"rich_text": {}},
        # optional human-readable label for quick inspection
        "value_label": {"rich_text": {}},
        # what kind of answer is stored
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
        # optional scored signal for ternary / signed questions
        "score": {"number": {"format": "number"}},
        # optional relation to ice_Questions
        "question": {
            "relation": {
                "database_id": ICE_QUESTIONS_DB_ID,
                "dual_property": {"synced_property_name": "responses"},
            }
        },
        # useful metadata for the paginated interaction flow
        "page_index": {"number": {"format": "number"}},
        "depth": {"number": {"format": "number"}},
        # optional free-text comment, especially for "Other"
        "optional_text": {"rich_text": {}},
        # safer generic timestamp naming
        "submitted_at": {"date": {}},
    }

    client.databases.update(
        database_id=ICE_RESPONSES_DB_ID,
        properties=props,
    )

    db = client.databases.retrieve(database_id=ICE_RESPONSES_DB_ID)
    print("\n[ice_Responses] current properties:")
    for k, v in db.get("properties", {}).items():
        print(f" - {k}: {v.get('type')}")

    print("\nSafe additive migration complete.")
    print("Legacy fields were left untouched.")
    print(
        "Start writing new interaction answers into: item_id, value_json, value_label, question_type, score, question, submitted_at."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
