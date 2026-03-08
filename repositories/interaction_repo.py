from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.base import InteractionRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_rich_text(props: Dict[str, Any], name: str) -> str:
    value = props.get(name) or {}
    parts = value.get("rich_text", []) if isinstance(value, dict) else []
    return "".join(part.get("plain_text", "") for part in parts if isinstance(part, dict))


def _extract_select_name(props: Dict[str, Any], name: str) -> str:
    value = props.get(name) or {}
    if isinstance(value, dict):
        sel = value.get("select") or {}
        if isinstance(sel, dict):
            return str(sel.get("name") or "")
    return ""


def _resolve_data_source_id(client: Any, db_or_ds_id: str) -> str:
    data_sources_endpoint = getattr(client, "data_sources", None)
    ds_retrieve = getattr(data_sources_endpoint, "retrieve", None) if data_sources_endpoint else None
    if callable(ds_retrieve):
        try:
            ds_retrieve(db_or_ds_id)
            return db_or_ds_id
        except Exception:
            pass

    databases_endpoint = getattr(client, "databases", None)
    db_retrieve = getattr(databases_endpoint, "retrieve", None) if databases_endpoint else None
    if callable(db_retrieve):
        db = db_retrieve(db_or_ds_id)
        data_sources = db.get("data_sources", []) if isinstance(db, dict) else []
        if data_sources and isinstance(data_sources[0], dict):
            ds_id = data_sources[0].get("id")
            if ds_id:
                return str(ds_id)
    return db_or_ds_id


class NotionInteractionRepository(InteractionRepository):
    def __init__(self, notion_repo: Any, database_id: str):
        if not notion_repo or not database_id:
            raise ValueError("Notion repo and database id are required.")
        self.repo = notion_repo
        self.client = notion_repo.client
        self.database_id = database_id
        self.data_source_id = _resolve_data_source_id(self.client, database_id)
        self._properties = self.client.data_sources.retrieve(self.data_source_id).get(
            "properties", {}
        )
        self._require_prop("session", "relation")
        self._require_prop("item_id", "rich_text")
        self._require_prop("question_type", "select")
        self._require_prop("value_json", "rich_text")
        self._require_prop("value_label", "rich_text")
        self._require_prop("submitted_at", "date")
        self._question_page_by_item_id: Dict[str, str] = {}

    def _find_prop(self, expected: str, ptype: Optional[str] = None) -> Optional[str]:
        if expected in self._properties:
            meta = self._properties.get(expected)
            if not ptype:
                return expected
            if isinstance(meta, dict) and meta.get("type") == ptype:
                return expected
        return None

    def _require_prop(self, expected: str, ptype: str) -> str:
        found = self._find_prop(expected, ptype)
        if not found:
            raise ValueError(
                f"Interaction Notion DB missing '{expected}' with type '{ptype}'."
            )
        return found

    @staticmethod
    def _derive_question_type(value: Any) -> str:
        if isinstance(value, dict):
            explicit = str(value.get("question_type") or "").strip().lower()
            if explicit in {"single", "multi", "text", "signal", "other"}:
                return explicit
            if str(value.get("type") or "").strip().lower() == "pre_signal":
                return "signal"
            answer = value.get("answer", value.get("choice"))
        else:
            answer = value
        if isinstance(answer, list):
            return "multi"
        if isinstance(answer, str):
            return "single"
        return "other"

    @staticmethod
    def _derive_value_label(value: Any) -> str:
        answer = value
        if isinstance(value, dict):
            answer = value.get("answer", value.get("choice", value))
        if isinstance(answer, list):
            return ", ".join(str(v) for v in answer if str(v).strip())
        if isinstance(answer, str):
            return answer
        try:
            return json.dumps(answer, ensure_ascii=False)
        except Exception:
            return str(answer)

    @staticmethod
    def _derive_score(value: Any) -> Optional[float]:
        if isinstance(value, dict):
            score = value.get("score")
            if isinstance(score, (int, float)):
                return float(score)
        return None

    @staticmethod
    def _derive_optional_text(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        optional_text = value.get("optional_text")
        if optional_text is None:
            optional_text = value.get("comment")
        return str(optional_text or "").strip()

    @staticmethod
    def _derive_page_index(value: Any) -> Optional[int]:
        if isinstance(value, dict) and isinstance(value.get("page_index"), (int, float)):
            return int(value.get("page_index"))
        return None

    @staticmethod
    def _derive_depth(value: Any) -> Optional[int]:
        if isinstance(value, dict) and isinstance(value.get("depth"), (int, float)):
            return int(value.get("depth"))
        return None

    def _resolve_question_page_id(self, question_id: str) -> Optional[str]:
        cached = self._question_page_by_item_id.get(question_id)
        if cached:
            return cached
        question_prop = self._find_prop("question", "relation")
        if not question_prop:
            return None
        question_meta = self._properties.get(question_prop) or {}
        relation_meta = question_meta.get("relation", {}) if isinstance(question_meta, dict) else {}
        target = relation_meta.get("data_source_id") or relation_meta.get("database_id")
        if not target:
            return None
        target_data_source_id = _resolve_data_source_id(self.client, str(target))
        target_props = self.client.data_sources.retrieve(target_data_source_id).get("properties", {})

        def _target_prop(name: str, ptype: str) -> Optional[str]:
            meta = target_props.get(name)
            if isinstance(meta, dict) and meta.get("type") == ptype:
                return name
            for n, m in target_props.items():
                if isinstance(m, dict) and m.get("type") == ptype:
                    return str(n)
            return None

        item_prop = _target_prop("item_id", "rich_text")
        title_prop = _target_prop("Name", "title")

        if item_prop:
            payload = self.client.data_sources.query(
                data_source_id=target_data_source_id,
                filter={"property": item_prop, "rich_text": {"equals": question_id}},
                page_size=1,
            )
            results = payload.get("results", [])
            if results:
                page_id = str(results[0].get("id", ""))
                if page_id:
                    self._question_page_by_item_id[question_id] = page_id
                    return page_id
        if title_prop:
            payload = self.client.data_sources.query(
                data_source_id=target_data_source_id,
                filter={"property": title_prop, "title": {"equals": question_id}},
                page_size=1,
            )
            results = payload.get("results", [])
            if results:
                page_id = str(results[0].get("id", ""))
                if page_id:
                    self._question_page_by_item_id[question_id] = page_id
                    return page_id
        return None

    def save_response(
        self,
        session_id: str,
        player_id: Optional[str],
        question_id: str,
        value: Any,
        text_id: str,
        device_id: str,
    ) -> None:
        session_prop = self._find_prop("session", "relation")
        player_prop = self._find_prop("player", "relation")
        question_prop = self._find_prop("question", "relation")
        item_prop = self._find_prop("item_id", "rich_text")
        value_json_prop = self._find_prop("value_json", "rich_text")
        value_label_prop = self._find_prop("value_label", "rich_text")
        question_type_prop = self._find_prop("question_type", "select")
        score_prop = self._find_prop("score", "number")
        submitted_prop = self._find_prop("submitted_at", "date")
        created_prop = self._find_prop("created_at", "date")
        page_index_prop = self._find_prop("page_index", "number")
        depth_prop = self._find_prop("depth", "number")
        optional_text_prop = self._find_prop("optional_text", "rich_text")
        text_prop = self._find_prop("text_id", "rich_text")
        device_prop = self._find_prop("device_id", "rich_text")
        title_prop = self._find_prop("Name", "title")

        properties: Dict[str, Any] = {}
        if session_prop:
            properties[session_prop] = {"relation": [{"id": session_id}]}
        if player_prop:
            properties[player_prop] = {"relation": [{"id": player_id}]} if player_id else {"relation": []}
        if question_prop:
            q_page_id = self._resolve_question_page_id(question_id)
            properties[question_prop] = {"relation": [{"id": q_page_id}]} if q_page_id else {"relation": []}
        if item_prop:
            properties[item_prop] = {"rich_text": [{"type": "text", "text": {"content": question_id}}]}
        if value_json_prop:
            properties[value_json_prop] = {
                "rich_text": [
                    {"type": "text", "text": {"content": json.dumps(value, ensure_ascii=False)}}
                ]
            }
        value_label = self._derive_value_label(value)
        if value_label_prop and value_label:
            properties[value_label_prop] = {
                "rich_text": [{"type": "text", "text": {"content": value_label}}]
            }
        question_type = self._derive_question_type(value)
        if question_type_prop:
            properties[question_type_prop] = {"select": {"name": question_type}}
        score = self._derive_score(value)
        if score_prop and score is not None:
            properties[score_prop] = {"number": score}
        page_index = self._derive_page_index(value)
        if page_index_prop and page_index is not None:
            properties[page_index_prop] = {"number": page_index}
        depth = self._derive_depth(value)
        if depth_prop and depth is not None:
            properties[depth_prop] = {"number": depth}
        optional_text = self._derive_optional_text(value)
        if optional_text_prop and optional_text:
            properties[optional_text_prop] = {
                "rich_text": [{"type": "text", "text": {"content": optional_text}}]
            }
        if submitted_prop:
            properties[submitted_prop] = {"date": {"start": _now_iso()}}
        if created_prop:
            properties[created_prop] = {"date": {"start": _now_iso()}}
        if text_prop:
            properties[text_prop] = {"rich_text": [{"type": "text", "text": {"content": text_id}}]}
        if device_prop:
            properties[device_prop] = {"rich_text": [{"type": "text", "text": {"content": device_id}}]}
        if title_prop:
            properties[title_prop] = {"title": [{"type": "text", "text": {"content": f"{question_id} · {text_id}"}}]}

        self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )

    def get_responses(self, session_id: str) -> List[Dict[str, Any]]:
        session_prop = self._find_prop("session", "relation")
        item_prop = self._find_prop("item_id", "rich_text")
        value_json_prop = self._find_prop("value_json", "rich_text")
        value_label_prop = self._find_prop("value_label", "rich_text")
        question_type_prop = self._find_prop("question_type", "select")
        score_prop = self._find_prop("score", "number")
        submitted_prop = self._find_prop("submitted_at", "date")
        created_prop = self._find_prop("created_at", "date")
        text_prop = self._find_prop("text_id", "rich_text")
        device_prop = self._find_prop("device_id", "rich_text")
        player_prop = self._find_prop("player", "relation")
        if not session_prop or not item_prop or not value_json_prop:
            return []

        out: List[Dict[str, Any]] = []
        next_cursor: Optional[str] = None
        while True:
            query: Dict[str, Any] = {
                "data_source_id": self.data_source_id,
                "filter": {"property": session_prop, "relation": {"contains": session_id}},
                "page_size": 100,
            }
            if next_cursor:
                query["start_cursor"] = next_cursor
            payload = self.client.data_sources.query(**query)
            for page in payload.get("results", []):
                props = page.get("properties", {})
                raw_value = _extract_rich_text(props, value_json_prop)
                parsed: Any
                try:
                    parsed = json.loads(raw_value)
                except Exception:
                    parsed = raw_value
                normalized_value = parsed
                if isinstance(parsed, dict):
                    if "answer" in parsed:
                        normalized_value = parsed.get("answer")
                    elif "choice" in parsed:
                        normalized_value = parsed.get("choice")
                player_ids = []
                pval = props.get(player_prop) if player_prop else None
                if isinstance(pval, dict):
                    player_ids = [x.get("id") for x in pval.get("relation", []) if isinstance(x, dict)]
                submitted = None
                if submitted_prop and isinstance(props.get(submitted_prop), dict):
                    submitted = (props.get(submitted_prop) or {}).get("date", {}).get("start")
                created = None
                if not submitted and created_prop and isinstance(props.get(created_prop), dict):
                    created = (props.get(created_prop) or {}).get("date", {}).get("start")
                score = None
                score_val = props.get(score_prop) if score_prop else None
                if isinstance(score_val, dict):
                    score = score_val.get("number")
                out.append(
                    {
                        "response_id": page.get("id"),
                        "session_id": session_id,
                        "player_id": player_ids[0] if player_ids else None,
                        "item_id": _extract_rich_text(props, item_prop),
                        "value": normalized_value,
                        "value_json": parsed,
                        "value_label": _extract_rich_text(props, value_label_prop) if value_label_prop else "",
                        "question_type": _extract_select_name(props, question_type_prop) if question_type_prop else "",
                        "score": score,
                        "text_id": _extract_rich_text(props, text_prop) if text_prop else "",
                        "device_id": _extract_rich_text(props, device_prop) if device_prop else "",
                        "created_at": submitted or created or page.get("created_time"),
                    }
                )
            if not payload.get("has_more"):
                break
            next_cursor = payload.get("next_cursor")
        return out
