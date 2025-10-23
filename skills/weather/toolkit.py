"""Weather tool fetching current conditions via the Open-Meteo API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import parse, request


class WeatherError(RuntimeError):
    """Raised when the weather API cannot satisfy the request."""


@dataclass
class WeatherReport:
    """Normalized weather information returned to the agent."""

    city: str
    country: Optional[str]
    latitude: float
    longitude: float
    temperature_c: float
    apparent_temperature_c: float
    humidity: Optional[float]
    wind_kmh: Optional[float]
    precipitation_mm: Optional[float]
    weather_code: Optional[int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "temperature_c": self.temperature_c,
            "apparent_temperature_c": self.apparent_temperature_c,
            "humidity": self.humidity,
            "wind_kmh": self.wind_kmh,
            "precipitation_mm": self.precipitation_mm,
            "weather_code": self.weather_code,
        }


def _http_get(url: str) -> Dict[str, Any]:
    with request.urlopen(url, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _geocode_city(city: str) -> Dict[str, Any]:
    query = parse.urlencode({"name": city, "count": 1, "language": "zh", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    data = _http_get(url)
    results = data.get("results") or []
    if not results:
        raise WeatherError(f"未找到城市 '{city}' 的地理位置，请换一个名称试试。")
    return results[0]


def _fetch_current_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "temperature_unit": "celsius",
        "windspeed_unit": "kmh",
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "precipitation",
                "rain",
                "weather_code",
            ]
        ),
    }
    url = f"https://api.open-meteo.com/v1/forecast?{parse.urlencode(params)}"
    return _http_get(url)


def fetch_weather(city: str) -> WeatherReport:
    """Return a structured weather report for the requested city."""

    city = (city or "").strip()
    if not city:
        raise WeatherError("城市名称不能为空。")

    geo = _geocode_city(city)
    weather = _fetch_current_weather(geo["latitude"], geo["longitude"])
    current = weather.get("current")
    if not current:
        raise WeatherError("天气服务暂时不可用，请稍后再试。")

    return WeatherReport(
        city=geo.get("name", city),
        country=geo.get("country"),
        latitude=float(geo["latitude"]),
        longitude=float(geo["longitude"]),
        temperature_c=float(current.get("temperature_2m")),
        apparent_temperature_c=float(current.get("apparent_temperature")),
        humidity=current.get("relative_humidity_2m"),
        wind_kmh=current.get("wind_speed_10m"),
        precipitation_mm=current.get("precipitation") or current.get("rain"),
        weather_code=current.get("weather_code"),
    )
