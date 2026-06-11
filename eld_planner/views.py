import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .routing import geocode, get_route
from .hos_engine import plan_trip
from .log_renderer import render_logs
from rest_framework.decorators import api_view


AVG_SPEED_MPH = 55.0  # conservative HGV average
ORS_KEY = os.getenv("ORS_API_KEY", "")


class PlanTripView(APIView):

    def post(self, request):
        try:
            current_loc  = request.data.get('current_location', '').strip()
            pickup_loc   = request.data.get('pickup_location', '').strip()
            dropoff_loc  = request.data.get('dropoff_location', '').strip()
            cycle_used   = float(request.data.get('cycle_used_hours', 0))
            carrier          = request.data.get('carrier', 'N/A').strip() or 'N/A'
            main_office      = request.data.get('main_office', 'N/A').strip() or 'N/A'
            tractor_number   = request.data.get('tractor_number', 'N/A').strip() or 'N/A'
            trailer_number   = request.data.get('trailer_number', 'N/A').strip() or 'N/A'
            driver_signature = request.data.get('driver_signature', 'Driver').strip() or 'Driver'
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid input. cycle_used_hours must be a number.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not all([current_loc, pickup_loc, dropoff_loc]):
            return Response(
                {'error': 'current_location, pickup_location, and dropoff_location are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (0 <= cycle_used <= 70):
            return Response(
                {'error': 'cycle_used_hours must be between 0 and 70.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 1. Geocode all three locations
            current_coords  = geocode(current_loc)   # [lng, lat]
            pickup_coords   = geocode(pickup_loc)
            dropoff_coords  = geocode(dropoff_loc)

            # 2. Get full route: current → pickup → dropoff
            route_data = get_route([current_coords, pickup_coords, dropoff_coords])

            total_miles       = route_data['total_miles']
            segment_miles     = route_data['segment_miles']  # [leg1, leg2]
            pickup_miles      = segment_miles[0] if len(segment_miles) > 0 else total_miles * 0.4
            dropoff_miles     = total_miles

            # 3. Build stop list with mileage markers
            stops = [
                {'type': 'pickup',  'miles': round(pickup_miles, 2),  'label': pickup_loc},
                {'type': 'dropoff', 'miles': round(dropoff_miles, 2), 'label': dropoff_loc},
            ]

            # Add fuel stops every 1,000 miles
            fuel_mark = 1000.0
            while fuel_mark < total_miles:
                # Skip if within 50 miles of an existing stop
                if not any(abs(s['miles'] - fuel_mark) < 50 for s in stops):
                    stops.append({
                        'type': 'fuel',
                        'miles': round(fuel_mark, 2),
                        'label': f'Mile {int(fuel_mark)} Fuel Stop',
                    })
                fuel_mark += 1000.0

            # 4. Run HOS engine
            days = plan_trip(
                total_miles=total_miles,
                avg_speed_mph=AVG_SPEED_MPH,
                stops=stops,
                cycle_used=cycle_used,
                home_terminal=current_loc,
                carrier=carrier,
                main_office=main_office,
                tractor_number=tractor_number,
                trailer_number=trailer_number,
                driver_signature=driver_signature,
            )

            # 5. Run log renderer
            logs = render_logs(days)

            # 6. Build stop markers for the map
            stop_markers = []
            cumulative = 0.0
            for seg_idx, seg_miles in enumerate(segment_miles):
                cumulative += seg_miles
                if seg_idx == 0:
                    stop_markers.append({
                        'type': 'pickup',
                        'label': pickup_loc,
                        'coords': [pickup_coords[1], pickup_coords[0]],  # [lat, lng] for Leaflet
                        'eta_hours': round(cumulative / AVG_SPEED_MPH, 2),
                    })
                else:
                    stop_markers.append({
                        'type': 'dropoff',
                        'label': dropoff_loc,
                        'coords': [dropoff_coords[1], dropoff_coords[0]],
                        'eta_hours': round(cumulative / AVG_SPEED_MPH, 2),
                    })

            return Response({
                'route': {
                    'geometry': route_data['geometry'],
                    'total_miles': total_miles,
                    'total_drive_hours': route_data['total_drive_hours'],
                    'stops': stop_markers,
                },
                'logs': logs,
            })

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'Server error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
# class GeocodeView(APIView):
#     """
#     Proxy ORS Pelias autocomplete so the API key stays server-side.
#     GET /api/geocode/?q=Chicago+IL
#     Returns GeoJSON FeatureCollection compatible with LocationAutocomplete.jsx
#     """
#     def get(self, request):
#         q = request.query_params.get("q", "").strip()
#         if not q or len(q) < 3:
#             return Response({"features": []})

#         try:
#             resp = requests.get(
#                 "https://api.openrouteservice.org/geocode/autocomplete",
#                 params={
#                     "api_key": ORS_KEY,
#                     "text": q,
#                     "size": 6,
#                     # Bias toward US/NA — remove if you want global results
#                     "boundary.country": "US,CA,MX",
#                 },
#                 timeout=5,
#             )
#             resp.raise_for_status()
#             return Response(resp.json())
#         except requests.RequestException as e:
#             return Response(
#                 {"error": str(e), "features": []},
#                 status=status.HTTP_502_BAD_GATEWAY,
#             )

@api_view(['GET'])
def GeocodeView(request):
    q = request.query_params.get('q', '').strip()
    if not q:
        return Response({'features': []})
    try:
        from .routing import geocode_search
        features = geocode_search(q)
        return Response({'features': features})
    except Exception as e:
        return Response({'features': [], 'error': str(e)})