from django.conf import settings
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from ..providers.errors import NoRouteError
from ..services import analysis
from ..services.factory import get_directions, get_weather
from .errors import err
from .serializers import HeatmapSerializer, TripSerializer


def _no_cache(response: Response) -> Response:
    """Mark critical API analysis responses as non-cacheable to prevent proxy leakage."""
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Pragma"] = "no-cache"
    return response


class AnalyzeThrottle(AnonRateThrottle):
    scope = "analyze"


class HeatmapThrottle(AnonRateThrottle):
    scope = "heatmap"


class GeocodeThrottle(AnonRateThrottle):
    scope = "geocode"


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request):
    q = (request.query_params.get("q") or "").strip()
    if not 2 <= len(q) <= 200:
        return err("invalid_request", "q must be 2-200 characters.", 400)
    results = get_directions().geocode(q)
    return Response({"results": [{"id": r.id, "name": r.name, "label": r.label, "lon": r.lon, "lat": r.lat}
                                 for r in results]})


@api_view(["POST"])
@throttle_classes([AnalyzeThrottle])
def analyze(request):
    s = TripSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    return _no_cache(Response(analysis.analyze_trip(
        origin=dict(d["origin"]), destination=dict(d["destination"]), departure=d["departure_time"],
        load_lb=d["load_lb"], interval=d["checkpoint_interval_miles"],
        directions=get_directions(), weather=get_weather())))


@api_view(["POST"])
@throttle_classes([HeatmapThrottle])
def heatmap(request):
    s = HeatmapSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    o, dest = d["origin"], d["destination"]
    routes = get_directions().get_routes((o["lon"], o["lat"]), (dest["lon"], dest["lat"]))  # cached
    if d["route_index"] >= len(routes):
        raise NoRouteError("That route is not available for this trip.")
    return _no_cache(Response(analysis.build_heatmap(
        route=routes[d["route_index"]], route_id=f"route-{d['route_index'] + 1}",
        departure=d["departure_time"], weather=get_weather())))
