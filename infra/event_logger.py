from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Dict, Optional

import streamlit as st

from infra.app_context import get_notion_repo


def get_module_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    return logging.getLogger(name)


def log_perf(module: str, metric: str, elapsed_ms: float, **details: Any) -> None:
    logger = get_module_logger(module)
    if details:
        detail_str = " ".join(f"{k}={details[k]}" for k in sorted(details.keys()))
        logger.info("perf.%s_ms=%.1f %s", metric, elapsed_ms, detail_str)
    else:
        logger.info("perf.%s_ms=%.1f", metric, elapsed_ms)


@contextmanager
def perf_timer(module: str, metric: str, **details: Any):
    started = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - started) * 1000.0
        log_perf(module, metric, elapsed_ms, **details)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _events_db_id() -> str:
    notion_cfg = st.secrets.get("notion", {})
    return str(
        notion_cfg.get("ice_events_db_id")
        or notion_cfg.get("events_db_id")
        or notion_cfg.get("events")
        or ""
    ).strip()


def _extract_rich_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if value.get("type") != "rich_text":
        return ""
    parts = value.get("rich_text", [])
    out = []
    for part in parts:
        if isinstance(part, dict):
            out.append(str(part.get("plain_text", "")))
    return "".join(out).strip()


def _extract_select_or_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    selected = value.get("select")
    if isinstance(selected, dict):
        return str(selected.get("name") or "")
    status_val = value.get("status")
    if isinstance(status_val, dict):
        return str(status_val.get("name") or "")
    return _extract_rich_text(value)


def _find_prop(props: Dict[str, Any], expected: str, ptype: Optional[str] = None) -> str:
    meta = props.get(expected)
    if isinstance(meta, dict) and (ptype is None or meta.get("type") == ptype):
        return expected
    for name, pmeta in props.items():
        if not isinstance(pmeta, dict):
            continue
        if ptype is None or pmeta.get("type") == ptype:
            if str(name).lower() == expected.lower():
                return str(name)
    return ""


@st.cache_resource(show_spinner=False)
def _event_repo_info() -> Dict[str, Any]:
    db_id = _events_db_id()
    repo = get_notion_repo()
    if not db_id or not repo:
        return {"enabled": False}
    try:
        data_sources = getattr(repo.client, "data_sources", None)
        ds_retrieve = (
            getattr(data_sources, "retrieve", None) if data_sources is not None else None
        )
        if callable(ds_retrieve):
            meta = ds_retrieve(db_id)
            return {
                "enabled": True,
                "repo": repo,
                "db_id": db_id,
                "props": meta.get("properties", {}) if isinstance(meta, dict) else {},
            }
    except Exception:
        pass
    return {"enabled": True, "repo": repo, "db_id": db_id, "props": {}}


def log_event(
    *,
    module: str,
    event_type: str,
    page: str = "",
    player_id: str = "",
    session_id: str = "",
    item_id: str = "",
    value_label: str = "",
    device_id: str = "",
    status: str = "ok",
    metadata: Optional[Dict[str, Any]] = None,
    level: str = "INFO",
) -> None:
    logger = get_module_logger(module)
    payload = {
        "event_type": event_type,
        "player_id": player_id,
        "session_id": session_id,
        "item_id": item_id,
        "value_label": value_label,
        "page": page,
        "device_id": device_id,
        "status": status,
        "metadata": metadata or {},
    }
    lvl = (level or "INFO").upper()
    if lvl == "ERROR":
        logger.error(json.dumps(payload, ensure_ascii=False))
    elif lvl == "WARNING":
        logger.warning(json.dumps(payload, ensure_ascii=False))
    else:
        logger.info(json.dumps(payload, ensure_ascii=False))

    info = _event_repo_info()
    if not info.get("enabled"):
        return
    repo = info.get("repo")
    db_id = str(info.get("db_id") or "")
    if not repo or not db_id:
        return

    props = info.get("props", {}) if isinstance(info.get("props"), dict) else {}
    timestamp_prop = _find_prop(props, "timestamp", "date") or _find_prop(
        props, "submitted_at", "date"
    )
    player_prop = _find_prop(props, "player", "relation")
    session_prop = _find_prop(props, "session", "relation")
    event_type_prop = _find_prop(props, "event_type", "select") or _find_prop(
        props, "event_type", "rich_text"
    )
    item_prop = _find_prop(props, "item_id", "rich_text")
    value_label_prop = _find_prop(props, "value_label", "rich_text")
    metadata_prop = _find_prop(props, "metadata_json", "rich_text")
    page_prop = _find_prop(props, "page", "rich_text")
    device_prop = _find_prop(props, "device_id", "rich_text")
    status_prop = _find_prop(props, "status", "select") or _find_prop(
        props, "status", "rich_text"
    )
    title_prop = (
        _find_prop(props, "Event", "title")
        or _find_prop(props, "Name", "title")
        or _find_prop(props, "Title", "title")
    )

    properties: Dict[str, Any] = {}
    now_iso = _now_iso()
    if timestamp_prop:
        properties[timestamp_prop] = {"date": {"start": now_iso}}
    if player_prop and player_id:
        properties[player_prop] = {"relation": [{"id": player_id}]}
    if session_prop and session_id:
        properties[session_prop] = {"relation": [{"id": session_id}]}
    if event_type_prop:
        if props.get(event_type_prop, {}).get("type") == "select":
            properties[event_type_prop] = {"select": {"name": event_type}}
        else:
            properties[event_type_prop] = {
                "rich_text": [{"type": "text", "text": {"content": event_type}}]
            }
    if item_prop and item_id:
        properties[item_prop] = {
            "rich_text": [{"type": "text", "text": {"content": item_id}}]
        }
    if value_label_prop and value_label:
        properties[value_label_prop] = {
            "rich_text": [{"type": "text", "text": {"content": value_label}}]
        }
    if page_prop and page:
        properties[page_prop] = {
            "rich_text": [{"type": "text", "text": {"content": page}}]
        }
    if device_prop and device_id:
        properties[device_prop] = {
            "rich_text": [{"type": "text", "text": {"content": device_id}}]
        }
    if status_prop and status:
        if props.get(status_prop, {}).get("type") == "select":
            properties[status_prop] = {"select": {"name": str(status)}}
        else:
            properties[status_prop] = {
                "rich_text": [{"type": "text", "text": {"content": str(status)}}]
            }
    if metadata_prop and metadata is not None:
        properties[metadata_prop] = {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": json.dumps(metadata, ensure_ascii=False)},
                }
            ]
        }
    if title_prop:
        scope = page or session_id or "app"
        properties[title_prop] = {
            "title": [
                {
                    "type": "text",
                    "text": {"content": f"{event_type} · {scope}"},
                }
            ]
        }

    try:
        repo.client.pages.create(parent={"database_id": db_id}, properties=properties)
    except Exception as exc:
        logger.error("Notion write failure for event stream: %s", exc)


def list_logged_events(
    *,
    page: str = "",
    session_id: str = "",
    limit: int = 100,
) -> list[Dict[str, Any]]:
    info = _event_repo_info()
    if not info.get("enabled"):
        return []
    repo = info.get("repo")
    db_id = str(info.get("db_id") or "")
    props = info.get("props", {}) if isinstance(info.get("props"), dict) else {}
    if not repo or not db_id:
        return []

    timestamp_prop = _find_prop(props, "timestamp", "date") or _find_prop(
        props, "submitted_at", "date"
    )
    player_prop = _find_prop(props, "player", "relation")
    session_prop = _find_prop(props, "session", "relation")
    event_type_prop = _find_prop(props, "event_type", "select") or _find_prop(
        props, "event_type", "rich_text"
    )
    item_prop = _find_prop(props, "item_id", "rich_text")
    value_label_prop = _find_prop(props, "value_label", "rich_text")
    metadata_prop = _find_prop(props, "metadata_json", "rich_text")
    page_prop = _find_prop(props, "page", "rich_text")
    device_prop = _find_prop(props, "device_id", "rich_text")
    status_prop = _find_prop(props, "status", "select") or _find_prop(
        props, "status", "rich_text"
    )

    filters: list[Dict[str, Any]] = []
    if page and page_prop:
        filters.append({"property": page_prop, "rich_text": {"equals": page}})
    if session_id and session_prop:
        filters.append({"property": session_prop, "relation": {"contains": session_id}})

    query_kwargs: Dict[str, Any] = {
        "page_size": limit,
        "sorts": [{"property": timestamp_prop, "direction": "descending"}]
        if timestamp_prop
        else [{"timestamp": "created_time", "direction": "descending"}],
    }
    if filters:
        query_kwargs["filter"] = {"and": filters} if len(filters) > 1 else filters[0]

    try:
        payload = repo.client.data_sources.query(data_source_id=db_id, **query_kwargs)
    except Exception:
        return []

    rows: list[Dict[str, Any]] = []
    for page_row in payload.get("results", []):
        row_props = page_row.get("properties", {})
        metadata_raw = _extract_rich_text(row_props.get(metadata_prop)) if metadata_prop else ""
        try:
            metadata = json.loads(metadata_raw) if metadata_raw else {}
        except Exception:
            metadata = {"raw": metadata_raw}
        rows.append(
            {
                "id": str(page_row.get("id", "")),
                "event_type": _extract_select_or_text(row_props.get(event_type_prop))
                if event_type_prop
                else "",
                "page": _extract_rich_text(row_props.get(page_prop)) if page_prop else "",
                "status": _extract_select_or_text(row_props.get(status_prop)) if status_prop else "",
                "item_id": _extract_rich_text(row_props.get(item_prop)) if item_prop else "",
                "value_label": _extract_rich_text(row_props.get(value_label_prop))
                if value_label_prop
                else "",
                "device_id": _extract_rich_text(row_props.get(device_prop)) if device_prop else "",
                "session_id": row_props.get(session_prop, {}).get("relation", [])[0].get("id", "")
                if session_prop and row_props.get(session_prop, {}).get("relation")
                else "",
                "player_id": row_props.get(player_prop, {}).get("relation", [])[0].get("id", "")
                if player_prop and row_props.get(player_prop, {}).get("relation")
                else "",
                "timestamp": row_props.get(timestamp_prop, {}).get("date", {}).get("start", "")
                if timestamp_prop
                else "",
                "metadata": metadata,
            }
        )
    return rows


def role_claim_cooldown_state(
    session_scope: str,
    max_attempts: int = 3,
    cooldown_minutes: int = 10,
) -> Dict[str, Any]:
    attempts_key = f"coorg_claim_attempts:{session_scope}"
    cooldown_key = f"coorg_claim_cooldown_until:{session_scope}"
    attempts = int(st.session_state.get(attempts_key, 0))
    cooldown_until_raw = st.session_state.get(cooldown_key)
    cooldown_until: Optional[datetime] = None
    if isinstance(cooldown_until_raw, str) and cooldown_until_raw:
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_raw)
        except Exception:
            cooldown_until = None
    now = datetime.now(timezone.utc)
    in_cooldown = bool(cooldown_until and now < cooldown_until)
    remaining = 0
    if in_cooldown and cooldown_until:
        remaining = int((cooldown_until - now).total_seconds())

    def record_failure() -> None:
        nonlocal attempts
        attempts += 1
        st.session_state[attempts_key] = attempts
        if attempts >= max_attempts:
            until = now + timedelta(minutes=cooldown_minutes)
            st.session_state[cooldown_key] = until.isoformat()

    def record_success() -> None:
        st.session_state[attempts_key] = 0
        st.session_state[cooldown_key] = ""

    return {
        "attempts": attempts,
        "max_attempts": max_attempts,
        "in_cooldown": in_cooldown,
        "remaining_seconds": remaining,
        "record_failure": record_failure,
        "record_success": record_success,
    }
