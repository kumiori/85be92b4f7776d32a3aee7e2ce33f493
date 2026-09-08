from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

import streamlit as st

from conference.semantic_fields import LocationValue


def opencage_location_options(payload: Any) -> list[LocationValue]:
    results = payload.get("results") if isinstance(payload, Mapping) else []
    options: list[LocationValue] = []
    for raw in results or []:
        if not isinstance(raw, Mapping):
            continue
        components = raw.get("components") if isinstance(raw.get("components"), Mapping) else {}
        geometry = raw.get("geometry") if isinstance(raw.get("geometry"), Mapping) else {}
        label = str(raw.get("formatted") or "").strip()
        if not label:
            continue
        locality = str(
            components.get("city")
            or components.get("town")
            or components.get("village")
            or components.get("municipality")
            or ""
        ).strip()
        region = str(components.get("state") or components.get("region") or "").strip()
        country = str(components.get("country") or "").strip()
        country_code = str(components.get("country_code") or "").strip().upper()
        annotations = raw.get("annotations") if isinstance(raw.get("annotations"), Mapping) else {}
        place_id = str(annotations.get("geohash") or "").strip()
        if not place_id:
            place_id = "opencage:" + hashlib.sha256(
                f"{label}:{geometry.get('lat')}:{geometry.get('lng')}".encode("utf-8")
            ).hexdigest()[:20]
        options.append(
            LocationValue(
                display_label=label,
                locality=locality,
                region=region,
                country=country,
                country_code=country_code,
                place_id=place_id,
                latitude=float(geometry["lat"]) if geometry.get("lat") is not None else None,
                longitude=float(geometry["lng"]) if geometry.get("lng") is not None else None,
            )
        )
    return options


def render_location_lookup(
    label: str,
    *,
    value: Any,
    key: str,
    lookup: Callable[[str], list[LocationValue]],
    optional: bool = True,
) -> dict[str, Any]:
    """Shared UI for every semantic location field."""
    current = dict(value) if isinstance(value, Mapping) else {}
    query = st.text_input(
        label,
        value=str(current.get("display_label") or ""),
        key=f"{key}_query",
        placeholder="Start typing a city or place",
    )
    token = str(query or "").strip()
    if not token:
        return {} if optional else current
    if token == str(current.get("display_label") or "") and current.get("place_id"):
        return current
    if len(token) < 3:
        st.caption("Type at least three characters, then choose a location.")
        return {}
    try:
        options = lookup(token)
    except Exception:
        st.warning("Location lookup is temporarily unavailable. Please try again.")
        return {}
    if not options:
        st.caption("No matching location found. Try a nearby city or a broader place name.")
        return {}
    selected = st.selectbox(
        "Choose a location",
        options,
        format_func=lambda item: item.display_label,
        index=None,
        key=f"{key}_choice",
        placeholder="Select the matching location",
    )
    return selected.as_dict() if isinstance(selected, LocationValue) else {}
