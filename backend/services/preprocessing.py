
import re


def preprocess_report(report):
    """Validate and standardize a weather report."""

    required_fields = ["city", "state", "text", "source"]

    for field in required_fields:
        if not report.get(field) or not isinstance(report[field], str):
            raise ValueError(f"Missing or invalid field: {field}")

    city = report["city"].strip().title()
    state = report["state"].strip().title()
    text = re.sub(r"\s+", " ", report["text"]).strip()
    source = report["source"].strip()

    latitude = report.get("latitude")
    longitude = report.get("longitude")

    if (latitude is None) != (longitude is None):
        raise ValueError("Both latitude and longitude must be provided")

    if latitude is not None:
        latitude = float(latitude)
        longitude = float(longitude)

        if not -90 <= latitude <= 90:
            raise ValueError("Invalid latitude")

        if not -180 <= longitude <= 180:
            raise ValueError("Invalid longitude")

    return {
        "city": city,
        "state": state,
        "text": text,
        "source": source,
        "latitude": latitude,
        "longitude": longitude,
        "observed_at": report.get("observed_at"),
        "weather_code": report.get("weather_code"),
        "weather_condition": report.get("weather_condition"),
        "weather_data": report.get("weather_data", {}),
    }
