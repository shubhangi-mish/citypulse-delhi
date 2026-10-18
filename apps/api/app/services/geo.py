"""Geographic helpers: generalisation, geocoding and OSM road lookup.

Geocoding uses Mapbox when a token is configured, else OSM Nominatim (respecting its 1 req/s policy).
Road lookup always uses Nominatim reverse geocoding because OSM data (ODbL) may be stored with attribution.
"""

import logging
import math
import threading
import time

import httpx

from app.core.config import get_settings

log = logging.getLogger("citypulse.geo")

# Rough bounding box of the NCT of Delhi (used to bias search and sanity-check coordinates).
DELHI_BBOX = (76.83, 28.40, 77.35, 28.89)  # min_lng, min_lat, max_lng, max_lat
DELHI_CENTER = (28.6139, 77.2090)
RADII_KM = (1, 3, 5, 10)

_nominatim_lock = threading.Lock()
_nominatim_last = 0.0


def in_delhi_region(lat: float, lng: float, margin: float = 0.15) -> bool:
    min_lng, min_lat, max_lng, max_lat = DELHI_BBOX
    return (min_lat - margin) <= lat <= (max_lat + margin) and (min_lng - margin) <= lng <= (max_lng + margin)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def generalise(lat: float, lng: float, precision: str) -> tuple[float, float]:
    """approximate ≈ 110 m grid; neighborhood ≈ 1.1 km grid (callers may substitute the neighborhood centre)."""
    digits = 3 if precision == "approximate" else 2
    return round(lat, digits), round(lng, digits)


def distance_bucket(meters: float) -> str:
    if meters < 500:
        return "under 0.5 km"
    for km in RADII_KM:
        if meters <= km * 1000:
            return f"within {km} km"
    return "over 10 km"


def _nominatim(path: str, params: dict) -> httpx.Response:
    global _nominatim_last
    with _nominatim_lock:
        wait = 1.05 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        _nominatim_last = time.monotonic()
        return httpx.get(f"https://nominatim.openstreetmap.org/{path}", params={**params, "format": "jsonv2"},
                         headers={"User-Agent": get_settings().user_agent}, timeout=8)


def search(query: str, limit: int = 6) -> dict:
    s = get_settings()
    min_lng, min_lat, max_lng, max_lat = DELHI_BBOX
    if s.geocoding_token:
        r = httpx.get(
            "https://api.mapbox.com/search/geocode/v6/forward",
            params={"q": query, "access_token": s.geocoding_token, "limit": limit, "country": "IN",
                    "proximity": f"{DELHI_CENTER[1]},{DELHI_CENTER[0]}",
                    "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}"},
            timeout=8,
        )
        r.raise_for_status()
        results = [
            {"label": f["properties"].get("full_address") or f["properties"].get("name"),
             "latitude": f["geometry"]["coordinates"][1], "longitude": f["geometry"]["coordinates"][0]}
            for f in r.json().get("features", [])
        ]
        return {"provider": "mapbox", "attribution": "© Mapbox", "results": results}
    r = _nominatim("search", {"q": query, "limit": limit, "countrycodes": "in", "bounded": 1,
                              "viewbox": f"{min_lng},{max_lat},{max_lng},{min_lat}"})
    r.raise_for_status()
    results = [{"label": x["display_name"], "latitude": float(x["lat"]), "longitude": float(x["lon"])}
               for x in r.json()]
    return {"provider": "nominatim", "attribution": "© OpenStreetMap contributors (ODbL)", "results": results}


def reverse_road(lat: float, lng: float) -> dict | None:
    """Nearest named OSM road at street zoom, or None. Best effort — failures never block a submission."""
    try:
        r = _nominatim("reverse", {"lat": lat, "lon": lng, "zoom": 17, "layer": "address"})
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # network, rate limit, parse
        log.info("reverse road lookup failed: %s", exc)
        return None
    address = data.get("address") or {}
    road_name = address.get("road")
    if data.get("osm_type") == "way" and data.get("category") == "highway" and data.get("name"):
        return {"osm_ref": f"way/{data['osm_id']}", "name": data["name"], "road_class": data.get("type")}
    if road_name:
        # Matched a building/POI: no way id, so key by road name + locality ("Main Road" repeats across Delhi).
        locality = address.get("suburb") or address.get("neighbourhood") or address.get("city_district") or ""
        return {"osm_ref": f"name/{road_name.lower()}|{locality.lower()}", "name": road_name, "road_class": None}
    return None
