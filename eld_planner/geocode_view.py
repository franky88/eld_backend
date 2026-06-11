"""
Add to eld_planner/views.py (or a new file geocode_view.py)
Then wire in urls.py: path("api/geocode/", GeocodeView.as_view())
"""
import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

ORS_KEY = os.getenv("ORS_API_KEY", "")

class GeocodeView(APIView):
    """
    Proxy ORS Pelias autocomplete so the API key stays server-side.
    GET /api/geocode/?q=Chicago+IL
    Returns GeoJSON FeatureCollection compatible with LocationAutocomplete.jsx
    """
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q or len(q) < 3:
            return Response({"features": []})

        try:
            resp = requests.get(
                "https://api.openrouteservice.org/geocode/autocomplete",
                params={
                    "api_key": ORS_KEY,
                    "text": q,
                    "size": 6,
                    # Bias toward US/NA — remove if you want global results
                    "boundary.country": "US,CA,MX",
                },
                timeout=5,
            )
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            return Response(
                {"error": str(e), "features": []},
                status=status.HTTP_502_BAD_GATEWAY,
            )