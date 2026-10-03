
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "showers",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
]


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail",
}


def fetch_weather(city, state, latitude, longitude):
    """
    Fetch current weather for a location from Open-Meteo.

    Returns a normalized report dictionary that can later
    be passed to VARUNA's preprocessing and AI pipeline.
    """

    if not city or not state:
        raise ValueError("City and state are required.")

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(CURRENT_FIELDS),
        "timezone": "UTC",
    }

    url = f"{BASE_URL}?{urlencode(params)}"

    request = Request(
        url,
        headers={"User-Agent": "VARUNA-Weather-Grid/1.0"}
    )

    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        raise RuntimeError(
            f"Weather API returned HTTP {error.code}."
        ) from error

    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            f"Could not connect to the weather API: {error}"
        ) from error

    current = data.get("current")

    if not current:
        raise RuntimeError("The API returned no current weather data.")

    weather_code = current.get("weather_code")
    condition = WEATHER_CODES.get(
        weather_code,
        "Unknown weather condition"
    )

    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind_speed = current.get("wind_speed_10m")
    precipitation = current.get("precipitation")

    details = [f"Current weather in {city}, {state}: {condition}"]

    if temperature is not None:
        details.append(f"Temperature: {temperature}°C")

    if humidity is not None:
        details.append(f"Humidity: {humidity}%")

    if wind_speed is not None:
        details.append(f"Wind speed: {wind_speed} km/h")

    if precipitation is not None:
        details.append(f"Precipitation: {precipitation} mm")

    return {
        "city": city,
        "state": state,
        "latitude": latitude,
        "longitude": longitude,
        "source": "Weather API (Open-Meteo)",
        "text": ". ".join(details) + ".",
        "observed_at": current.get("time"),
        "weather_code": weather_code,
        "weather_condition": condition,
        "weather_data": current,
    }
