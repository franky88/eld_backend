import os
import requests
from dotenv import load_dotenv

load_dotenv()

ORS_KEY = os.getenv('ORS_API_KEY')
ORS_BASE = 'https://api.openrouteservice.org'

if not ORS_KEY:
    raise RuntimeError("ORS_API_KEY is missing in environment variables")

print("ORS_KEY:", ORS_KEY)


def geocode(location: str) -> list:
    """Convert a city/state string to [lng, lat]."""
    url = f"{ORS_BASE}/geocode/search"
    params = {
        'api_key': ORS_KEY,
        'text': location,
        'size': 1,
    }
    r = requests.get(url, params=params, timeout=10)
    if not r.ok:
        print("ORS GEO ERROR:", r.status_code, r.text)
        r.raise_for_status()
    features = r.json().get('features', [])
    if not features:
        raise ValueError(f"Could not geocode location: {location}")
    coords = features[0]['geometry']['coordinates']  # [lng, lat]
    return coords


def get_route(coords_list: list) -> dict:
    """
    Get driving route between a list of [lng, lat] coordinates.
    Returns distance in miles, duration in hours, encoded polyline geometry,
    and per-segment distances in miles derived from way_points.
    """
    url = f"{ORS_BASE}/v2/directions/driving-hgv"
    headers = {
        'Authorization': ORS_KEY,
        'Content-Type': 'application/json',
        "User-Agent": "django-render-app/1.0"
    }
    body = {
        'coordinates': coords_list,
        'geometry': True,
        'instructions': True,  # needed to get step distances for segments
    }
    r = requests.post(url, json=body, headers=headers, timeout=15)
    if not r.ok:
        print("ORS ROUTE ERROR:", r.status_code, r.text)
        r.raise_for_status()

    data = r.json()
    route = data['routes'][0]

    total_miles = route['summary']['distance'] * 0.000621371
    total_hours = route['summary']['duration'] / 3600

    # ── Derive per-segment distances using way_points ────────────────────────
    # way_points: indices into the steps array marking where each waypoint falls
    # e.g. [0, 1521, 3723] means leg 1 = steps[0..1521], leg 2 = steps[1521..3723]
    # We use the cumulative distance at each way_point step to get leg distances.
    way_points = route.get('way_points', [])
    steps = []
    for seg in route.get('segments', []):
        steps.extend(seg.get('steps', []))

    segment_miles = []
    if way_points and len(way_points) >= 2 and steps:
        # Build cumulative distance array over all steps
        cumulative = [0.0]
        for step in steps:
            cumulative.append(cumulative[-1] + step.get('distance', 0.0))

        for i in range(len(way_points) - 1):
            start_idx = way_points[i]
            end_idx   = way_points[i + 1]
            # Clamp to available steps
            start_idx = min(start_idx, len(cumulative) - 1)
            end_idx   = min(end_idx,   len(cumulative) - 1)
            leg_dist_m = cumulative[end_idx] - cumulative[start_idx]
            segment_miles.append(leg_dist_m * 0.000621371)
    else:
        # Fallback: split proportionally if no step data
        n = len(coords_list) - 1
        segment_miles = [total_miles / n] * n if n > 0 else [total_miles]

    return {
        'total_miles': round(total_miles, 2),
        'total_drive_hours': round(total_hours, 2),
        'geometry': route['geometry'],  # encoded polyline
        'segment_miles': segment_miles,
    }

def geocode_search(query: str, size: int = 5) -> list:
    """Return raw ORS geocode features for autocomplete."""

    url = f"{ORS_BASE}/geocode/autocomplete"

    headers = {
        "Accept": "application/json, application/geo+json"
    }

    params = {
        "api_key": ORS_KEY,
        "text": query,
        "size": size
    }

    r = requests.get(url, params=params, headers=headers, timeout=8)

    if not r.ok:
        print("ORS GEO ERROR:", r.status_code, r.text)
        raise Exception(r.text)

    return r.json().get("features", [])