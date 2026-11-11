from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GeocodeResult:
    id: str
    name: str
    label: str
    lon: float
    lat: float


@dataclass(frozen=True)
class RouteOption:
    distance_m: float
    duration_s: float
    coords: tuple                              # ((lon, lat), ...) - actual provider geometry
    segment_durations_s: Optional[tuple] = None  # one per coordinate pair, if provided
