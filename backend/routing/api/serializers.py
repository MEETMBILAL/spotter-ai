from datetime import datetime, timedelta, timezone

from rest_framework import serializers

from ..domain.geo import ALLOWED_INTERVALS, haversine_miles


class LocationSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200, allow_blank=True, default="")
    lon = serializers.FloatField(min_value=-180, max_value=180)
    lat = serializers.FloatField(min_value=-90, max_value=90)


class TripSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure_time = serializers.CharField(max_length=40)
    load_lb = serializers.FloatField(min_value=0, max_value=200_000)
    checkpoint_interval_miles = serializers.ChoiceField(choices=list(ALLOWED_INTERVALS), default=25)

    def validate_departure_time(self, value):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise serializers.ValidationError("Use ISO 8601, e.g. 2026-11-12T08:00:00-06:00")
        if dt.tzinfo is None:
            raise serializers.ValidationError("departure_time must include a UTC offset or 'Z'.")
        now = datetime.now(timezone.utc)
        if dt < now - timedelta(days=1) or dt > now + timedelta(days=16):
            raise serializers.ValidationError("departure_time must be within the forecast window (-1 to +16 days).")
        return dt.astimezone(timezone.utc)

    def validate(self, data):
        o, d = data["origin"], data["destination"]
        if haversine_miles((o["lon"], o["lat"]), (d["lon"], d["lat"])) < 0.5:
            raise serializers.ValidationError("Origin and destination must be different locations.")
        return data


class HeatmapSerializer(TripSerializer):
    route_index = serializers.IntegerField(min_value=0, max_value=2, default=0)
