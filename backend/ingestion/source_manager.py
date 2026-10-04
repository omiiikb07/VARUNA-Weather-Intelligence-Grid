from datetime import datetime, timezone

from ingestion.weather_api import fetch_weather
from services.preprocessing import preprocess_report


# Representative city coverage for the VARUNA SIH demo prototype.
# Coordinates are city reference points, not station-level observations.
INDIAN_CITIES = [
    {"city": "Bengaluru", "state": "Karnataka", "latitude": 12.9716, "longitude": 77.5946},
    {"city": "Mysuru", "state": "Karnataka", "latitude": 12.2958, "longitude": 76.6394},
    {"city": "Mangaluru", "state": "Karnataka", "latitude": 12.9141, "longitude": 74.8560},
    {"city": "Hubballi", "state": "Karnataka", "latitude": 15.3647, "longitude": 75.1240},
    {"city": "Chennai", "state": "Tamil Nadu", "latitude": 13.0827, "longitude": 80.2707},
    {"city": "Coimbatore", "state": "Tamil Nadu", "latitude": 11.0168, "longitude": 76.9558},
    {"city": "Hyderabad", "state": "Telangana", "latitude": 17.3850, "longitude": 78.4867},
    {"city": "Visakhapatnam", "state": "Andhra Pradesh", "latitude": 17.6868, "longitude": 83.2185},
    {"city": "Vijayawada", "state": "Andhra Pradesh", "latitude": 16.5062, "longitude": 80.6480},
    {"city": "Kochi", "state": "Kerala", "latitude": 9.9312, "longitude": 76.2673},
    {"city": "Thiruvananthapuram", "state": "Kerala", "latitude": 8.5241, "longitude": 76.9366},
    {"city": "Mumbai", "state": "Maharashtra", "latitude": 19.0760, "longitude": 72.8777},
    {"city": "Pune", "state": "Maharashtra", "latitude": 18.5204, "longitude": 73.8567},
    {"city": "Nagpur", "state": "Maharashtra", "latitude": 21.1458, "longitude": 79.0882},
    {"city": "Ahmedabad", "state": "Gujarat", "latitude": 23.0225, "longitude": 72.5714},
    {"city": "Jaipur", "state": "Rajasthan", "latitude": 26.9124, "longitude": 75.7873},
    {"city": "Jodhpur", "state": "Rajasthan", "latitude": 26.2389, "longitude": 73.0243},
    {"city": "New Delhi", "state": "Delhi", "latitude": 28.6139, "longitude": 77.2090},
    {"city": "Lucknow", "state": "Uttar Pradesh", "latitude": 26.8467, "longitude": 80.9462},
    {"city": "Varanasi", "state": "Uttar Pradesh", "latitude": 25.3176, "longitude": 82.9739},
    {"city": "Bhopal", "state": "Madhya Pradesh", "latitude": 23.2599, "longitude": 77.4126},
    {"city": "Kolkata", "state": "West Bengal", "latitude": 22.5726, "longitude": 88.3639},
    {"city": "Bhubaneswar", "state": "Odisha", "latitude": 20.2961, "longitude": 85.8245},
    {"city": "Patna", "state": "Bihar", "latitude": 25.5941, "longitude": 85.1376},
    {"city": "Guwahati", "state": "Assam", "latitude": 26.1445, "longitude": 91.7362},
]


def collect_weather(locations=None):
    """Fetch and preprocess current weather for configured Indian cities."""
    if locations is None:
        locations = INDIAN_CITIES

    reports = []
    errors = []

    for location in locations:
        city = location["city"]
        state = location["state"]
        try:
            raw_report = fetch_weather(
                city=city,
                state=state,
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
            report = preprocess_report(raw_report)
            reports.append(report)
            print(f"Collected and preprocessed weather for {city}, {state}")
        except Exception as error:
            errors.append({"city": city, "state": state, "error": str(error)})
            print(f"Failed to collect weather for {city}: {error}")

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_locations": len(locations),
        "successful": len(reports),
        "failed": len(errors),
        "reports": reports,
        "errors": errors,
    }
