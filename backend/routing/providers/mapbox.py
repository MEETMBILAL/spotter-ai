"""Mapbox Geocoding (v6) + Directions (driving profile). Server-side token only.

NOTE: the `driving` profile is ordinary car routing. It does NOT account for truck height,
weight, axle or hazmat restrictions. This module never claims otherwise.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

import requests
from django.core.cache import cache as default_cache

from .errors import (NoRouteError, ProviderConfigError, ProviderResponseError, ProviderTimeout,
                     ProviderUnavailable)
from .models import GeocodeResult, RouteOption

log = logging.getLogger(__name__)
GEOCODE_URL = "https://api.mapbox.com/search/geocode/v6/forward"
DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{coords}"
ROUTES_TTL_S, GEOCODE_TTL_S = 900, 3600


class MapboxClient:
    def __init__(self, token: str, timeout: float = 10.0, session=None, cache=None):
        self.token, self.timeout = token, timeout
        self.session = session or requests.Session()
        self.cache = cache or default_cache

    def _get(self, url: str, params: dict) -> dict:
        if not self.token:
            raise ProviderConfigError("Mapbox token is not configured on the server")
        try:
            r = self.session.get(url, params={**params, "access_token": self.token}, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderTimeout("Mapbox request timed out") from None
        except requests.RequestException as exc:
            # Log only the exception type: request URLs (and so tokens) can appear in messages.
            log.warning("Mapbox request failed: %s", type(exc).__name__)
            raise ProviderUnavailable("Could not reach Mapbox") from None
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code in (401, 403):
            raise ProviderConfigError("Mapbox rejected the server token")
        if r.status_code >= 400 or (isinstance(data, dict) and data.get("code") in ("NoRoute", "NoSegment")):
            if isinstance(data, dict) and data.get("code") in ("NoRoute", "NoSegment"):
                raise NoRouteError("No drivable route was found between these locations")
            raise ProviderUnavailable(f"Mapbox returned HTTP {r.status_code}")
        if not isinstance(data, dict):
            raise ProviderResponseError("Unexpected Mapbox response")
        return data

    # ---------------------------------------------------------------- geocoding
    def geocode(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        key = "mb:geo:" + hashlib.sha1(query.strip().lower().encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        data = self._get(GEOCODE_URL, {"q": query, "limit": limit, "autocomplete": "true"})
        out = []
        for f in data.get("features", []):
            try:
                lon, lat = (float(x) for x in f["geometry"]["coordinates"][:2])
                p = f.get("properties", {})
                label = p.get("full_address") or ", ".join(x for x in (p.get("name"), p.get("place_formatted")) if x)
                out.append(GeocodeResult(str(p.get("mapbox_id", f.get("id", ""))), p.get("name") or label, label, lon, lat))
            except (KeyError, TypeError, ValueError):
                continue  # skip malformed feature rather than failing the whole search
        self.cache.set(key, out, GEOCODE_TTL_S)
        return out

    # --------------------------------------------------------------- directions
    def get_routes(self, origin: tuple, destination: tuple) -> list[RouteOption]:
        """origin/destination are (lon, lat). Returns genuine provider routes (max 3), de-duplicated."""
        key = "mb:dir:" + hashlib.sha1(
            f"{origin[0]:.5f},{origin[1]:.5f};{destination[0]:.5f},{destination[1]:.5f}".encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        coords = f"{origin[0]:.6f},{origin[1]:.6f};{destination[0]:.6f},{destination[1]:.6f}"
        data = self._get(DIRECTIONS_URL.format(coords=coords), {
            "alternatives": "true", "geometries": "geojson", "overview": "full",
            "annotations": "duration"})
        routes: list[RouteOption] = []
        for r in data.get("routes", []):
            try:
                geom = tuple((float(c[0]), float(c[1])) for c in r["geometry"]["coordinates"])
                if len(geom) < 2:
                    continue
                seg = None
                legs = r.get("legs", [])
                if legs and all("annotation" in l and "duration" in l["annotation"] for l in legs):
                    seg = tuple(float(d) for l in legs for d in l["annotation"]["duration"])
                opt = RouteOption(float(r["distance"]), float(r["duration"]), geom, seg)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            if not any(_same_route(opt, o) for o in routes):  # drop exact duplicates only
                routes.append(opt)
        if not routes:
            raise NoRouteError("No drivable route was found between these locations")
        routes = routes[:3]
        self.cache.set(key, routes, ROUTES_TTL_S)
        return routes


def _same_route(a: RouteOption, b: RouteOption) -> bool:
    return (abs(a.distance_m - b.distance_m) < 10 and abs(a.duration_s - b.duration_s) < 1
            and len(a.coords) == len(b.coords))
