from django.conf import settings

from ..providers.mapbox import MapboxClient
from ..providers.open_meteo import OpenMeteoClient
from ..providers.protocols import DirectionsProvider, WeatherProvider


def get_directions() -> DirectionsProvider:
    return MapboxClient(settings.MAPBOX_SERVER_TOKEN, settings.PROVIDER_TIMEOUT_S)


def get_weather() -> WeatherProvider:
    return OpenMeteoClient(settings.PROVIDER_TIMEOUT_S)
