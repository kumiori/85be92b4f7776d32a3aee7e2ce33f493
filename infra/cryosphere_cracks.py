from __future__ import annotations

from typing import Any


CRYOSPHERE_CRACKS: dict[str, list[dict[str, Any]]] = {
    "Ice Shelves (Antarctica)": [
        {
            "Region": "Ross Ice Shelf",
            "Latitude": -82.0,
            "Longitude": 175.0,
            "Elastic_Energy": 7,
        },
        {
            "Region": "Ronne Ice Shelf",
            "Latitude": -78.5,
            "Longitude": -60.0,
            "Elastic_Energy": 6,
        },
        {
            "Region": "Larsen C Ice Shelf",
            "Latitude": -67.5,
            "Longitude": -60.0,
            "Elastic_Energy": 8,
        },
        {
            "Region": "Amery Ice Shelf",
            "Latitude": -69.0,
            "Longitude": 70.0,
            "Elastic_Energy": 6,
        },
    ],
    "Glaciers (Greenland & High Altitudes)": [
        {
            "Region": "Jakobshavn Glacier",
            "Latitude": 69.2,
            "Longitude": -49.8,
            "Elastic_Energy": 9,
        },
        {
            "Region": "Helheim Glacier",
            "Latitude": 66.3,
            "Longitude": -38.1,
            "Elastic_Energy": 8,
        },
        {
            "Region": "Karakoram Glaciers",
            "Latitude": 35.0,
            "Longitude": 75.0,
            "Elastic_Energy": 7,
        },
    ],
    "Sea Ice (Arctic Ocean)": [
        {
            "Region": "Beaufort Sea",
            "Latitude": 73.0,
            "Longitude": -130.0,
            "Elastic_Energy": 4,
        },
        {
            "Region": "Laptev Sea",
            "Latitude": 75.0,
            "Longitude": 130.0,
            "Elastic_Energy": 3,
        },
    ],
    "Permafrost Regions (Northern Hemisphere)": [
        {
            "Region": "Siberia",
            "Latitude": 65.0,
            "Longitude": 120.0,
            "Elastic_Energy": 5,
        }
    ],
    "Subglacial Lakes and Basal Ice (Antarctica)": [
        {
            "Region": "Lake Vostok",
            "Latitude": -77.5,
            "Longitude": 106.8,
            "Elastic_Energy": 8,
        }
    ],
}


def cryosphere_crack_points(energy_scale: int = 10) -> list[dict[str, float | str]]:
    points: list[dict[str, float | str]] = []
    for entries in CRYOSPHERE_CRACKS.values():
        for entry in entries:
            longitude = entry.get("Longitude")
            if longitude is None:
                continue
            points.append(
                {
                    "name": str(entry["Region"]),
                    "lat": float(entry["Latitude"]),
                    "lng": float(longitude),
                    "energy": float(entry["Elastic_Energy"]) * energy_scale,
                }
            )
    return points
