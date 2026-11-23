import logging
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_forecast():
    cached = cache.get("forecast")
    if cached is not None:
        return cached
    params = {
        "latitude": settings.CITY_LAT,
        "longitude": settings.CITY_LON,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Europe/Kyiv",
        "forecast_days": 16,
    }
    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=8)
        resp.raise_for_status()
        daily = resp.json()["daily"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        log.warning("Open-Meteo недоступний: %s", exc)
        return {}
    forecast = {}
    for i, day in enumerate(daily["time"]):
        forecast[day] = {
            "t_max": daily["temperature_2m_max"][i],
            "t_min": daily["temperature_2m_min"][i],
            "rain": daily["precipitation_probability_max"][i],
        }
    cache.set("forecast", forecast, 60 * 60 * 3)
    return forecast


def day_weather(day: date):
    return fetch_forecast().get(day.isoformat())


def is_bad_for_outdoor(weather):
    if not weather:
        return False
    rain = weather.get("rain") or 0
    t_max = weather.get("t_max")
    if rain >= 60:
        return True
    if t_max is not None and (t_max <= -5 or t_max >= 32):
        return True
    return False


def describe(weather):
    if not weather:
        return ""
    t = round(weather["t_max"]) if weather.get("t_max") is not None else None
    parts = []
    if t is not None:
        parts.append(f"до {t:+d}°C")
    if weather.get("rain") is not None:
        parts.append(f"дощ {weather['rain']}%")
    return ", ".join(parts)
