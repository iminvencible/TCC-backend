"""Geographic containment for warning delivery within São Paulo state."""

import json
from functools import lru_cache
from pathlib import Path


def ring_state(longitude: float, latitude: float, ring: list[list[float]]) -> int:
    inside = False
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][:2]
        x2, y2 = ring[index + 1][:2]
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if (
            abs(cross) <= 1e-9
            and min(x1, x2) - 1e-9 <= longitude <= max(x1, x2) + 1e-9
            and min(y1, y2) - 1e-9 <= latitude <= max(y1, y2) + 1e-9
        ):
            return 2
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
    return 1 if inside else 0


def point_in_polygon(longitude: float, latitude: float, geometry: dict) -> bool:
    if geometry.get("type") != "Polygon":
        return False
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or not rings or len(rings[0]) < 4:
        return False
    outer = ring_state(longitude, latitude, rings[0])
    if outer == 0:
        return False
    if outer == 2:
        return True
    for hole in rings[1:]:
        state = ring_state(longitude, latitude, hole)
        if state == 2:
            return True
        if state == 1:
            return False
    return True


@lru_cache(maxsize=1)
def sao_paulo_geometry() -> dict:
    # Shared with the map; bundled IBGE boundary avoids a live network dependency.
    path = Path(__file__).resolve().parent.parent / "public/assets/data/sao-paulo.geojson"
    return json.loads(path.read_text(encoding="utf-8"))["features"][0]["geometry"]


def point_in_sao_paulo(longitude: float, latitude: float) -> bool:
    geometry = sao_paulo_geometry()
    if geometry.get("type") == "MultiPolygon":
        return any(
            point_in_polygon(longitude, latitude, {"type": "Polygon", "coordinates": rings})
            for rings in geometry["coordinates"]
        )
    return point_in_polygon(longitude, latitude, geometry)
