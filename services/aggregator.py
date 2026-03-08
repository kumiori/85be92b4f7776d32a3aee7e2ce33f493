from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infra.app_context import load_config
from services.presence import count_active_users
from services.response_reader import fetch_session_responses


def _extract_choice(payload: Any) -> Any:
    if isinstance(payload, dict):
        if "answer" in payload:
            return payload.get("answer")
        if "choice" in payload:
            return payload.get("choice")
    return payload


def _guess_type(rows_for_item: list[Dict[str, Any]]) -> str:
    counts = Counter()
    for row in rows_for_item:
        qtype = str(row.get("question_type") or "").strip().lower()
        if qtype:
            counts[qtype] += 1
            continue
        payload = row.get("value_json")
        choice = _extract_choice(payload)
        if isinstance(choice, list):
            counts["multi"] += 1
        elif isinstance(choice, str):
            counts["single"] += 1
        else:
            counts["other"] += 1
    if not counts:
        return "other"
    return counts.most_common(1)[0][0]


def _actor_key(row: Dict[str, Any]) -> str:
    pid = str(row.get("player_id") or "").strip()
    if pid:
        return f"player:{pid}"
    did = str(row.get("device_id") or "").strip()
    if did:
        return f"device:{did}"
    rid = str(row.get("response_id") or "").strip()
    if rid:
        return f"response:{rid}"
    return "unknown"


def _latest_rows(rows_for_item: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    latest: dict[str, Dict[str, Any]] = {}
    for row in sorted(rows_for_item, key=lambda r: str(r.get("submitted_at") or "")):
        latest[_actor_key(row)] = row
    return list(latest.values())


def aggregate_question(rows_for_item: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows_for_item:
        return {}
    item_id = str(rows_for_item[0].get("item_id", ""))
    qtype = _guess_type(rows_for_item)
    latest_rows = _latest_rows(rows_for_item)

    if qtype == "signal":
        label_counts = Counter()
        scores: list[float] = []
        timeline: list[Dict[str, Any]] = []
        for row in latest_rows:
            payload = row.get("value_json")
            choice = _extract_choice(payload)
            label = str(choice or row.get("value_label") or "Other")
            label_counts[label] += 1
            score = row.get("score")
            if isinstance(payload, dict) and isinstance(payload.get("score"), (int, float)):
                score = payload.get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
                timeline.append({"t": row.get("submitted_at", ""), "score": float(score)})
        for row in rows_for_item:
            payload = row.get("value_json")
            score = row.get("score")
            if isinstance(payload, dict) and isinstance(payload.get("score"), (int, float)):
                score = payload.get("score")
            if isinstance(score, (int, float)):
                timeline.append({"t": row.get("submitted_at", ""), "score": float(score)})
        return {
            "item_id": item_id,
            "question_type": "signal",
            "chart_type": "signal_distribution",
            "n_responses": len(latest_rows),
            "n_events": len(rows_for_item),
            "counts": dict(label_counts),
            "scores": {
                "mean": (sum(scores) / len(scores)) if scores else 0.0,
                "sum": sum(scores),
                "n_scored": len(scores),
            },
            "timeline": [x for x in timeline if x["t"]],
        }

    if qtype == "multi":
        counts = Counter()
        for row in latest_rows:
            payload = row.get("value_json")
            choice = _extract_choice(payload)
            if not isinstance(choice, list):
                continue
            for token in choice:
                token_txt = str(token or "").strip()
                if token_txt:
                    counts[token_txt] += 1
        return {
            "item_id": item_id,
            "question_type": "multi",
            "chart_type": "emotion_frequency",
            "n_responses": len(latest_rows),
            "n_events": len(rows_for_item),
            "counts": dict(counts),
        }

    if qtype == "text":
        entries = []
        for row in latest_rows:
            payload = row.get("value_json")
            choice = _extract_choice(payload)
            txt = str(choice or row.get("value_label") or "").strip()
            if txt:
                entries.append({"t": row.get("submitted_at", ""), "text": txt})
        entries = sorted(entries, key=lambda x: x.get("t", ""), reverse=True)[:20]
        return {
            "item_id": item_id,
            "question_type": "text",
            "chart_type": "latest_text",
            "n_responses": len(latest_rows),
            "n_events": len(rows_for_item),
            "entries": entries,
        }

    counts = Counter()
    for row in latest_rows:
        payload = row.get("value_json")
        choice = _extract_choice(payload)
        label = str(choice or row.get("value_label") or "").strip()
        if label:
            if "maybe" in label.lower():
                label = "Maybe"
            counts[label] += 1
    return {
        "item_id": item_id,
        "question_type": "single",
        "chart_type": "choice_distribution",
        "n_responses": len(latest_rows),
        "n_events": len(rows_for_item),
        "counts": dict(counts),
    }


def aggregate_session(session_slug: Optional[str]) -> Dict[str, Any]:
    session, rows = fetch_session_responses(session_slug=session_slug)
    if not session:
        return {
            "session_slug": "",
            "session_name": "",
            "active_users": 0,
            "participant_count": 0,
            "response_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "questions": [],
        }

    grouped: dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        item_id = str(row.get("item_id", "")).strip()
        if not item_id:
            continue
        grouped.setdefault(item_id, []).append(row)

    cfg = load_config() or {}
    window = int(((cfg.get("overview") or {}).get("active_user_window_minutes")) or 10)
    session_name = str(session.get("session_code") or "Session")
    session_slug_norm = str(rows[0].get("session_slug")) if rows else session_name.lower()

    participant_ids = {_actor_key(r) for r in rows if _actor_key(r) != "unknown"}

    return {
        "session_slug": session_slug_norm,
        "session_name": session_name,
        "active_users": count_active_users(window, session_id=str(session.get("id", ""))),
        "participant_count": len(participant_ids),
        "response_count": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "questions": [aggregate_question(v) for _, v in sorted(grouped.items())],
    }


def export_session_aggregate_json(session_slug: Optional[str]) -> Dict[str, Any]:
    return aggregate_session(session_slug)


def get_overview_payload(session_slug: str) -> Dict[str, Any]:
    return export_session_aggregate_json(session_slug)
