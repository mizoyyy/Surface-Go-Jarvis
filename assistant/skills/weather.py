"""Weather from Open-Meteo (free, no API key)."""

import httpx

from .. import config
from .common import day_phrase, resolve_day

WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
    81: "rain showers", 82: "heavy rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


def geocode(name):
    r = httpx.get("https://geocoding-api.open-meteo.com/v1/search", timeout=10,
                  params={"name": name, "count": 5, "language": "en", "format": "json"})
    r.raise_for_status()
    return [{"name": g["name"], "country": g.get("country", ""), "admin": g.get("admin1", ""),
             "latitude": g["latitude"], "longitude": g["longitude"]} for g in r.json().get("results", [])]


def forecast(lat, lon):
    imperial = config.settings.get("units") == "imperial"
    r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "temperature_unit": "fahrenheit" if imperial else "celsius",
        "wind_speed_unit": "mph" if imperial else "kmh"})
    r.raise_for_status()
    data = r.json()
    cur, daily = data["current"], data["daily"]
    return {
        "current": {"temp": round(cur["temperature_2m"]), "feels": round(cur["apparent_temperature"]),
                    "code": cur["weather_code"], "text": WMO.get(cur["weather_code"], ""),
                    "wind": round(cur["wind_speed_10m"]), "is_day": cur["is_day"]},
        "days": [{"date": daily["time"][i], "code": daily["weather_code"][i],
                  "text": WMO.get(daily["weather_code"][i], ""),
                  "max": round(daily["temperature_2m_max"][i]), "min": round(daily["temperature_2m_min"][i]),
                  "rain": daily["precipitation_probability_max"][i]} for i in range(len(daily["time"]))],
        "unit": "°F" if imperial else "°C",
    }


def home_forecast():
    loc = config.settings.get("location")
    data = forecast(loc["latitude"], loc["longitude"])
    data["place"] = loc["name"]
    return data


def get_weather(day="today", location=None):
    if location:
        places = geocode(location)
        if not places:
            return f"I couldn't find {location}."
        place = places[0]
        data, name = forecast(place["latitude"], place["longitude"]), place["name"]
    else:
        data, name = home_forecast(), None
    where = f" in {name}" if name else ""
    target = resolve_day(day).isoformat()
    if day == "today":
        cur, today = data["current"], data["days"][0]
        text = (f"It's {cur['temp']} degrees and {cur['text']}{where}, "
                f"with a high of {today['max']} and a low of {today['min']}.")
        if today["rain"] and today["rain"] >= 40:
            text += f" There's a {today['rain']} percent chance of rain."
        return text
    for d in data["days"]:
        if d["date"] == target:
            text = f"{day_phrase(day).capitalize()}{where}: {d['text']}, high of {d['max']} and low of {d['min']}."
            if d["rain"] and d["rain"] >= 30:
                text += f" {d['rain']} percent chance of rain."
            return text
    return "I only have the forecast for the next week."
