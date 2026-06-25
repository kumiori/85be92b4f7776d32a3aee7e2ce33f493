from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List


def _listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _fingerprint(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = max(0, min(5, int(raw)))
        except Exception:
            continue
    return out


def count_field(submissions: Iterable[Dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for row in submissions:
        value = row.get(field)
        if isinstance(value, list):
            for item in value:
                if str(item).strip():
                    counter[str(item).strip()] += 1
        elif isinstance(value, str) and value.strip():
            counter[value.strip()] += 1
    return counter


def room_snapshot(submissions: List[Dict[str, Any]]) -> Dict[str, Any]:
    countries = {
        str(item.get("scientific_home_country") or "").strip()
        for item in submissions
        if str(item.get("scientific_home_country") or "").strip()
    }
    return {
        "participants": len(submissions),
        "countries": len(countries),
        "assets": count_field(submissions, "assets"),
        "motivations": count_field(submissions, "motivations"),
        "obstacles": count_field(submissions, "obstacle"),
        "challenges": count_field(submissions, "challenge"),
        "follow_up": count_field(submissions, "follow_up_interest"),
    }


def _shared_tokens(left: Iterable[str], right: Iterable[str]) -> list[str]:
    return sorted(set(_listify(list(left))) & set(_listify(list(right))))


def _dominant_fingerprint_axes(value: Any) -> list[str]:
    fp = _fingerprint(value)
    if not fp:
        return []
    max_score = max(fp.values()) if fp else 0
    if max_score <= 0:
        return []
    return sorted([axis for axis, score in fp.items() if score == max_score])


def neighbour_candidates(current: Dict[str, Any], submissions: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    current_actor = str(current.get("actor_key") or "")
    current_role = _listify(current.get("role", []))
    current_assets = _listify(current.get("assets", []))
    current_fp = _dominant_fingerprint_axes(current.get("complexity_fingerprint"))

    ranked: List[Dict[str, Any]] = []
    for candidate in submissions:
        if str(candidate.get("actor_key") or "") == current_actor:
            continue

        score = 0
        reasons: List[str] = []

        shared_role = sorted(set(current_role) & set(_listify(candidate.get("role", []))))
        if shared_role:
            score += len(shared_role) * 2
            reasons.append(f"shared perspective: {', '.join(shared_role)}")

        shared_assets = sorted(set(current_assets) & set(_listify(candidate.get("assets", []))))
        if shared_assets:
            score += len(shared_assets) * 2
            reasons.append(f"shared assets: {', '.join(shared_assets)}")

        if str(current.get("scale") or "").strip() and str(current.get("scale") or "").strip() == str(candidate.get("scale") or "").strip():
            score += 1
            reasons.append("same computational scale")

        if str(current.get("collaboration_style") or "").strip() and str(current.get("collaboration_style") or "").strip() == str(candidate.get("collaboration_style") or "").strip():
            score += 1
            reasons.append("similar collaboration style")

        if str(current.get("career_stage") or "").strip() and str(current.get("career_stage") or "").strip() == str(candidate.get("career_stage") or "").strip():
            score += 1
            reasons.append("similar career stage")

        shared_fp = sorted(set(current_fp) & set(_dominant_fingerprint_axes(candidate.get("complexity_fingerprint"))))
        if shared_fp:
            score += 1
            reasons.append(f"shared confidence signal: {', '.join(shared_fp)}")

        if score <= 0:
            continue

        ranked.append(
            {
                "actor_key": candidate.get("actor_key", ""),
                "access_key_last4": str(candidate.get("access_key_last4") or "").strip(),
                "score": score,
                "reasons": reasons[:3],
                "identity_available": bool(
                    str(candidate.get("identity") or "").strip()
                    or str(candidate.get("alias") or "").strip()
                ),
            }
        )

    ranked.sort(
        key=lambda item: (
            -int(item.get("score", 0)),
            str(item.get("access_key_last4") or ""),
            str(item.get("actor_key") or ""),
        )
    )
    return ranked[:limit]
