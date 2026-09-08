from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LocationValue:
    display_label: str
    locality: str = ""
    region: str = ""
    country: str = ""
    country_code: str = ""
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", None)}


def normalize_location_value(value: Any) -> LocationValue:
    if not isinstance(value, Mapping):
        raise ValueError("Choose a location from the shared location lookup.")
    display_label = str(value.get("display_label") or value.get("formatted") or "").strip()
    place_id = str(
        value.get("place_id")
        or value.get("provider_place_id")
        or value.get("provider_id")
        or value.get("geocode_id")
        or ""
    ).strip()
    if not display_label or not place_id:
        raise ValueError("Choose a location from the shared location lookup.")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    return LocationValue(
        display_label=display_label,
        locality=str(value.get("locality") or value.get("city") or "").strip(),
        region=str(value.get("region") or value.get("state") or "").strip(),
        country=str(value.get("country") or "").strip(),
        country_code=str(value.get("country_code") or "").strip().upper(),
        place_id=place_id,
        latitude=float(latitude) if latitude not in (None, "") else None,
        longitude=float(longitude) if longitude not in (None, "") else None,
    )
