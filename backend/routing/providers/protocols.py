"""Explicit structural typing contracts for provider clients.

Using typing.Protocol (PEP 544) means any class with the right methods
satisfies the contract without inheritance — ideal for mocking in tests.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence, runtime_checkable

from .models import GeocodeResult, RouteOption


@runtime_checkable
class DirectionsProvider(Protocol):
    """Geocoding + routing provider contract."""

    def geocode(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        """Return geocoding results for a free-text query."""
        ...

    def get_routes(self, origin: tuple, destination: tuple) -> list[RouteOption]:
        """Return up to 3 genuine driving routes between two (lon, lat) points."""
        ...


@runtime_checkable
class WeatherProvider(Protocol):
    """Hourly weather forecast provider contract."""

    def get_hourly(self, points: Sequence[tuple], start: date, end: date) -> list:
        """Return HourlySeries for each (lat, lon) point in the given date range."""
        ...
