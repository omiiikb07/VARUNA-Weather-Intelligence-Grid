
from datetime import datetime, timezone

from ingestion.weather_api import fetch_weather
from services.preprocessing import preprocess_report


# Initial locations for the VARUNA prototype
INDIAN_CITIES = [
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
    },
    {
        "city": "Mysuru",
        "state": "Karnataka",
        "latitude": 12.2958,
        "longitude": 76.6394,
    },
    {
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
    },
    {
        "city": "Jaipur",
        "state": "Rajasthan",
        "latitude": 26.9124,
        "longitude": 75.7873,
    },
    {
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
    },
]


def collect_weather(locations=None):
    """
    Fetch current weather for configured Indian cities.

    Preprocesses each report and returns successful reports
    along with any collection errors.
    """

    if locations is None:
        locations = INDIAN_CITIES

    reports = []
    errors = []

    for location in locations:
        city = location["city"]
        state = location["state"]

        try:
            # Fetch raw weather data
            raw_report = fetch_weather(
                city=city,
                state=state,
                latitude=location["latitude"],
                longitude=location["longitude"],
            )

            # Validate and standardize the report
            report = preprocess_report(raw_report)

            # Store the processed report in the results
            reports.append(report)

            print(
                f"Collected and preprocessed weather "
                f"for {city}, {state}"
            )

        except Exception as error:
            errors.append({
                "city": city,
                "state": state,
                "error": str(error),
            })

            print(f"Failed to collect weather for {city}: {error}")

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_locations": len(locations),
        "successful": len(reports),
        "failed": len(errors),
        "reports": reports,
        "errors": errors,
    }
