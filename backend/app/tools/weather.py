import json
from typing import Literal

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from app.core.config import (
    EXTERNAL_API_TIMEOUT_SECONDS,
    OPENWEATHER_API_KEY,
    OPENWEATHER_CURRENT_URL,
    OPENWEATHER_GEOCODING_URL,
    WEATHER_API_KEY,
    WEATHERAPI_CURRENT_URL,
)


class WeatherInput(BaseModel):
    location: str = Field(description="City or location to get current weather for.")
    units: Literal["metric", "imperial", "standard"] = Field(
        default="metric",
        description="Temperature and wind-speed unit system.",
    )

    @field_validator("units", mode="before")
    @classmethod
    def preserve_metric_fallback(cls, value):
        if value not in {"metric", "imperial", "standard"}:
            return "metric"
        return value


def _weatherapi_result(weather: dict, units: str) -> dict:
    location = weather.get("location", {})
    current = weather.get("current", {})
    condition = current.get("condition", {})

    if units == "imperial":
        temperature = current.get("temp_f")
        feels_like = current.get("feelslike_f")
        wind_speed = current.get("wind_mph")
    elif units == "standard":
        temperature_c = current.get("temp_c")
        feels_like_c = current.get("feelslike_c")
        wind_kph = current.get("wind_kph")
        temperature = temperature_c + 273.15 if temperature_c is not None else None
        feels_like = feels_like_c + 273.15 if feels_like_c is not None else None
        wind_speed = wind_kph / 3.6 if wind_kph is not None else None
    else:
        temperature = current.get("temp_c")
        feels_like = current.get("feelslike_c")
        wind_kph = current.get("wind_kph")
        wind_speed = wind_kph / 3.6 if wind_kph is not None else None

    return {
        "location": location.get("name"),
        "state": location.get("region"),
        "country": location.get("country"),
        "condition": condition.get("text"),
        "temperature": temperature,
        "feels_like": feels_like,
        "humidity_percent": current.get("humidity"),
        "wind_speed": wind_speed,
        "units": units,
    }


@tool(args_schema=WeatherInput)
def get_live_weather(location: str, units: str = "metric") -> str:
    """
    Get current live weather for a city or location.
    Units can be metric, imperial, or standard.
    """

    if not WEATHER_API_KEY and not OPENWEATHER_API_KEY:
        return (
            "Weather tool is not configured. Add WEATHER_API_KEY to backend/.env."
        )

    location = location.strip()
    if not location:
        return "Weather lookup requires a city or location."

    if units not in {"metric", "imperial", "standard"}:
        units = "metric"

    try:
        with httpx.Client(timeout=EXTERNAL_API_TIMEOUT_SECONDS) as client:
            if WEATHER_API_KEY:
                response = client.get(
                    WEATHERAPI_CURRENT_URL,
                    params={
                        "key": WEATHER_API_KEY,
                        "q": location,
                        "aqi": "no",
                    },
                )
                if response.status_code == 400:
                    error = response.json().get("error", {})
                    if error.get("code") == 1006:
                        return f"No weather location found for '{location}'."
                response.raise_for_status()
                return json.dumps(
                    _weatherapi_result(response.json(), units),
                    ensure_ascii=False,
                )

            geocoding_response = client.get(
                OPENWEATHER_GEOCODING_URL,
                params={
                    "q": location,
                    "limit": 1,
                    "appid": OPENWEATHER_API_KEY,
                },
            )
            geocoding_response.raise_for_status()
            locations = geocoding_response.json()

            if not locations:
                return f"No weather location found for '{location}'."

            place = locations[0]
            weather_response = client.get(
                OPENWEATHER_CURRENT_URL,
                params={
                    "lat": place["lat"],
                    "lon": place["lon"],
                    "appid": OPENWEATHER_API_KEY,
                    "units": units,
                },
            )
            weather_response.raise_for_status()
            weather = weather_response.json()

        main = weather.get("main", {})
        wind = weather.get("wind", {})
        conditions = weather.get("weather", [])
        condition = conditions[0] if conditions else {}

        result = {
            "location": weather.get("name") or place.get("name") or location,
            "state": place.get("state"),
            "country": weather.get("sys", {}).get("country") or place.get("country"),
            "condition": condition.get("description"),
            "temperature": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity_percent": main.get("humidity"),
            "wind_speed": wind.get("speed"),
            "units": units,
        }
        return json.dumps(result, ensure_ascii=False)
    except httpx.TimeoutException:
        return "Weather service timed out. Please try again."
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return "Weather service could not complete the request. Please try again."
