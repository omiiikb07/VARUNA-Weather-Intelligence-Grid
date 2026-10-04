
from datetime import datetime, timezone, timedelta


VALID_WEATHER_CODES = {
    0, 1, 2, 3, 45, 48,
    51, 53, 55, 56, 57,
    61, 63, 65, 66, 67,
    71, 73, 75, 77,
    80, 81, 82, 85, 86,
    95, 96, 99
}

# Weather codes that provide contextual support for event types.
EVENT_SUPPORT = {
    "Thunderstorm": {95, 96, 99},
    "Heavy Rainfall": {65, 67, 82},
    "Fog": {45, 48},
    "Hailstorm": {96, 99},
    "Light Rain": {51, 56, 61, 66, 80},
    "Moderate Rain": {53, 63, 81},
    "Snow": {71, 73, 75, 77, 85, 86},
    "Clear Sky": {0},
    "Mainly Clear": {1},
    "Partly Cloudy": {2},
    "Overcast": {3},
}

# Limited explicit conflicts. These are not proof that a report is false.
EVENT_CONFLICTS = {
    "Thunderstorm": {0, 1},
    "Heavy Rainfall": {0, 1},
    "Fog": {0, 1, 2, 3},
    "Clear Sky": {45, 48, 95, 96, 99},
    "Mainly Clear": {45, 48, 95, 96, 99},
    "Partly Cloudy": {95, 96, 99},
    "Overcast": {0},
}


def to_utc_naive(value):
    """Convert a datetime or ISO timestamp to naive UTC."""
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(
                timezone.utc
            ).replace(tzinfo=None)

        return parsed
    except (ValueError, TypeError):
        return None


def valid_number(value, minimum, maximum):
    """Check whether a value is numeric and within range."""
    if isinstance(value, bool):
        return False

    try:
        number = float(value)
        return minimum <= number <= maximum
    except (ValueError, TypeError):
        return False


def assess_weather_api_detailed(report, observed_at=None):
    """
    Validate the supplied Open-Meteo label, payload structure,
    coordinate values, measurements and observation timestamp.

    This is a plausibility check, not independent confirmation
    of real-world weather or cryptographic source authentication.
    """
    evidence = []
    score = 0

    source = (report.get("source") or "").strip().casefold()
    if source != "weather api (open-meteo)":
        return {
            "status": "Uncertain",
            "score": 0,
            "reason": "Unrecognized weather API source.",
            "evidence": ["Source label was not recognized."]
        }

    evidence.append("Source label matches Open-Meteo.")
    score += 20

    data = report.get("weather_data")
    if not isinstance(data, dict) or not data:
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Missing or invalid weather data.",
            "evidence": evidence + ["Weather payload is missing or invalid."]
        }

    evidence.append("Weather payload is a non-empty object.")
    score += 20

    latitude = report.get("latitude")
    longitude = report.get("longitude")
    if (
        not valid_number(latitude, -90, 90)
        or not valid_number(longitude, -180, 180)
    ):
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Invalid or missing coordinates.",
            "evidence": evidence + ["Coordinates failed validation."]
        }

    evidence.append("Coordinates are within valid geographic ranges.")
    score += 20

    code = data.get("weather_code")
    if (
        isinstance(code, bool)
        or not valid_number(code, 0, 99)
        or int(float(code)) not in VALID_WEATHER_CODES
        or float(code) != int(float(code))
    ):
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Missing or unsupported weather code.",
            "evidence": evidence + ["Weather code failed validation."]
        }

    evidence.append("Weather code is supported.")
    score += 20

    checks = {
        "temperature_2m": (-90, 65),
        "relative_humidity_2m": (0, 100),
        "wind_speed_10m": (0, 300),
        "precipitation": (0, 1000),
        "rain": (0, 1000),
        "showers": (0, 1000),
        "cloud_cover": (0, 100),
        "wind_direction_10m": (0, 360),
    }

    for field, (low, high) in checks.items():
        value = data.get(field)
        if value is not None and not valid_number(value, low, high):
            return {
                "status": "Uncertain",
                "score": score,
                "reason": f"Invalid measurement: {field}.",
                "evidence": evidence + [
                    f"Measurement {field} failed range validation."
                ]
            }

    evidence.append("Available numeric measurements passed range checks.")
    score += 10

    timestamp = to_utc_naive(observed_at or data.get("time"))
    if timestamp is None:
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Missing or invalid observation time.",
            "evidence": evidence + ["Observation time is unavailable."]
        }

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age = now - timestamp

    if age < -timedelta(minutes=15):
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Observation time is in the future.",
            "evidence": evidence + ["Timestamp is too far in the future."]
        }

    if age > timedelta(hours=6):
        return {
            "status": "Uncertain",
            "score": score,
            "reason": "Weather observation is stale.",
            "evidence": evidence + ["Observation is older than six hours."]
        }

    evidence.append("Observation timestamp is within the accepted age window.")
    score += 10

    return {
        "status": "Source Validated",
        "score": min(score, 100),
        "reason": (
            "Open-Meteo payload passed basic source-label, structure, "
            "coordinate, measurement and timestamp checks. "
            "Conditions are not independently verified."
        ),
        "evidence": evidence
    }


def assess_weather_api(report, observed_at=None):
    """Backward-compatible assessment interface."""
    result = assess_weather_api_detailed(report, observed_at)
    return result["status"], result["reason"]


def observation_supports_event(event_type, weather_data):
    """Check whether an observation's WMO code supports an event."""
    if not isinstance(weather_data, dict):
        return False

    code = weather_data.get("weather_code")
    try:
        if isinstance(code, bool):
            return False
        code = int(code)
    except (ValueError, TypeError):
        return False

    return code in EVENT_SUPPORT.get(event_type, set())


def observation_conflicts_with_event(event_type, weather_data):
    """Identify a limited set of clear contextual conflicts."""
    if not isinstance(weather_data, dict):
        return False

    code = weather_data.get("weather_code")
    try:
        if isinstance(code, bool):
            return False
        code = int(code)
    except (ValueError, TypeError):
        return False

    return code in EVENT_CONFLICTS.get(event_type, set())


def assess_citizen_report_detailed(event_type, observations):
    """
    Score available contextual evidence for a citizen report.

    The score is an evidence indicator, not a statistical
    probability that the report is true.
    """
    evidence = []
    matching = 0
    conflicting = 0
    usable = 0

    if event_type in {"Unknown", "Flood", "Heatwave", "Dust Storm"}:
        return {
            "status": "Uncertain",
            "score": 0,
            "reason": (
                f"{event_type} cannot be reliably assessed "
                "using the currently available weather observations."
            ),
            "evidence": [
                "Required event-specific evidence is not currently available."
            ]
        }

    for observation in observations:
        data = observation.weather_data or {}
        if not isinstance(data, dict):
            continue

        code = data.get("weather_code")
        try:
            if isinstance(code, bool) or int(code) not in VALID_WEATHER_CODES:
                continue
        except (ValueError, TypeError):
            continue

        usable += 1

        if observation_supports_event(event_type, data):
            matching += 1
        elif observation_conflicts_with_event(event_type, data):
            conflicting += 1

    if usable == 0:
        return {
            "status": "Uncertain",
            "score": 0,
            "reason": (
                "No usable recent weather observations were available "
                "for comparison."
            ),
            "evidence": ["No comparable observations were found."]
        }

    evidence.append(f"{usable} usable observation(s) compared.")

    # A single matching observation is limited contextual evidence.
    if matching:
        score = min(55 + (matching - 1) * 10, 75)
        evidence.append(
            f"{matching} observation(s) were consistent with the event."
        )
        return {
            "status": "Weather-Supported",
            "score": score,
            "reason": (
                "Available weather observations are consistent with "
                "the report. This is contextual support, not independent "
                "confirmation."
            ),
            "evidence": evidence
        }

    # Conflicting context alone is not enough to prove a report false.
    if conflicting:
        score = 20
        evidence.append(
            f"{conflicting} observation(s) showed potentially conflicting "
            "weather context."
        )
        return {
            "status": "Uncertain",
            "score": score,
            "reason": (
                "Available observations may conflict with the report, "
                "but this is insufficient to conclude that it is false."
            ),
            "evidence": evidence
        }

    return {
        "status": "Uncertain",
        "score": 30,
        "reason": (
            "Observations were available, but they did not provide "
            "clear supporting or contradictory evidence."
        ),
        "evidence": evidence + [
            "No clear event-specific match was identified."
        ]
    }


def assess_citizen_report(event_type, observations):
    """Backward-compatible assessment interface."""
    result = assess_citizen_report_detailed(event_type, observations)
    return result["status"], result["reason"]
