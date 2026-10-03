
import re
from difflib import SequenceMatcher
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime


# Routine conditions are observations, not active severe events.
OBSERVATION_TYPES = {
    "unknown",
    "unclassified",
    "clear sky",
    "mainly clear",
    "partly cloudy",
    "overcast",
    "light rain",
    "moderate rain",
    "snow",
}


def get_value(report, key, default=None):
    """Read a field from either a dictionary or a report object."""
    if isinstance(report, dict):
        return report.get(key, default)
    return getattr(report, key, default)


def normalize_text(text):
    """Normalize text for exact duplicate detection."""
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_similarity(text):
    """Normalize report text for near-duplicate comparison."""
    return normalize_text(text)


def calculate_similarity(text1, text2):
    """Return text similarity as a percentage."""
    normalized1 = normalize_for_similarity(text1)
    normalized2 = normalize_for_similarity(text2)

    if not normalized1 or not normalized2:
        return 0

    return round(
        SequenceMatcher(None, normalized1, normalized2).ratio() * 100
    )


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates using Haversine."""
    earth_radius_km = 6371.0

    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )

    a = max(0, min(1, a))
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius_km * c


def parse_timestamp(value):
    """Convert supported timestamp values to datetime."""
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None


def find_near_duplicates(reports):
    """
    Identify potential near-duplicate reports.

    Reports are compared using text similarity, time and GPS context.
    Missing time or GPS context is flagged as PARTIAL.
    """
    near_duplicate_pairs = []

    for i in range(len(reports)):
        report1 = reports[i]

        text1 = get_value(report1, "text", "") or ""
        city1 = (get_value(report1, "city", "") or "").casefold()
        state1 = (get_value(report1, "state", "") or "").casefold()

        lat1 = get_value(report1, "latitude")
        lon1 = get_value(report1, "longitude")
        time1 = parse_timestamp(get_value(report1, "timestamp"))

        if len(normalize_for_similarity(text1)) < 20:
            continue

        for j in range(i + 1, len(reports)):
            report2 = reports[j]

            text2 = get_value(report2, "text", "") or ""
            city2 = (get_value(report2, "city", "") or "").casefold()
            state2 = (get_value(report2, "state", "") or "").casefold()

            lat2 = get_value(report2, "latitude")
            lon2 = get_value(report2, "longitude")
            time2 = parse_timestamp(get_value(report2, "timestamp"))

            if len(normalize_for_similarity(text2)) < 20:
                continue

            # Compare only reports from the same city and state.
            if city1 != city2:
                continue

            if state1 and state2 and state1 != state2:
                continue

            similarity = calculate_similarity(text1, text2)

            if similarity < 72:
                continue

            # Reject reports that are too far apart in time.
            time_difference_minutes = None

            if time1 and time2:
                # Handle timestamps with and without timezone data.
                if time1.tzinfo != time2.tzinfo:
                    time1 = time1.replace(tzinfo=None)
                    time2 = time2.replace(tzinfo=None)

                time_difference_minutes = abs(
                    (time2 - time1).total_seconds()
                ) / 60

                if time_difference_minutes > 360:
                    continue

            # Reject reports that are too far apart geographically.
            distance_km = None

            has_gps1 = lat1 is not None and lon1 is not None
            has_gps2 = lat2 is not None and lon2 is not None

            if has_gps1 and has_gps2:
                distance_km = calculate_distance_km(
                    lat1, lon1, lat2, lon2
                )

                if distance_km > 10:
                    continue

            # Missing either time or GPS makes the match partial.
            context_status = (
                "COMPLETE"
                if time_difference_minutes is not None
                and distance_km is not None
                else "PARTIAL"
            )

            near_duplicate_pairs.append({
                "report_id_1": get_value(report1, "id"),
                "report_id_2": get_value(report2, "id"),
                "similarity": similarity,
                "time_difference_minutes": (
                    round(time_difference_minutes, 2)
                    if time_difference_minutes is not None
                    else None
                ),
                "distance_km": (
                    round(distance_km, 2)
                    if distance_km is not None
                    else None
                ),
                "context_status": context_status,
                "status": "POTENTIAL_DUPLICATE",
            })

    return near_duplicate_pairs


def create_event_summary(reports):
    """
    Group reports by city, state and event type and generate summaries.

    Exact duplicates are counted separately. Near duplicates are flagged
    but are not removed from the report counts.

    Event confidence is a heuristic score, not a probability.
    ACTIVE indicates a classified event, not independent verification
    or confirmation that it is currently occurring.
    """
    grouped_reports = {}

    # Group reports by city, state and event type.
    for report in reports:
        city = get_value(report, "city", "Unknown") or "Unknown"
        event_type = (
            get_value(report, "event_type", "Unknown") or "Unknown"
        )
        state = get_value(report, "state", "") or ""

        group_key = (
            city.casefold(),
            state.casefold(),
            event_type.casefold(),
        )

        if group_key not in grouped_reports:
            grouped_reports[group_key] = {
                "city": city,
                "state": state,
                "event_type": event_type,
                "reports": [],
            }

        grouped_reports[group_key]["reports"].append(report)

    events = []

    for group in grouped_reports.values():
        city = group["city"]
        state = group["state"]
        event_type = group["event_type"]
        submitted_reports = group["reports"]

        # Remove exact duplicate text from the unique report list.
        unique_reports = []
        seen_texts = set()

        for report in submitted_reports:
            text = get_value(report, "text", "") or ""
            normalized = normalize_text(text)

            if normalized not in seen_texts:
                seen_texts.add(normalized)
                unique_reports.append(report)

        report_count = len(unique_reports)
        submitted_report_count = len(submitted_reports)
        duplicate_count = submitted_report_count - report_count

        # Flag near duplicates among exact-unique reports.
        near_duplicate_pairs = find_near_duplicates(unique_reports)
        near_duplicate_count = len(near_duplicate_pairs)

        # Count verification statuses from all submitted reports.
        verification_counts = {
            "verified": 0,
            "pending": 0,
            "under_review": 0,
            "rejected": 0,
        }

        for report in submitted_reports:
            verification_status = (
                get_value(report, "verification_status", "Pending")
                or "Pending"
            ).strip().casefold()

            if verification_status == "verified":
                verification_counts["verified"] += 1
            elif verification_status == "under review":
                verification_counts["under_review"] += 1
            elif verification_status == "rejected":
                verification_counts["rejected"] += 1
            else:
                verification_counts["pending"] += 1

        # Average trust score over exact-unique reports.
        trust_scores = [
            float(get_value(report, "trust_score", 0) or 0)
            for report in unique_reports
        ]

        average_trust = (
            sum(trust_scores) / len(trust_scores)
            if trust_scores
            else 0
        )

        # Heuristic confidence based on trust and report volume.
        confidence = min(
            int(average_trust + min(report_count * 2, 15)),
            99,
        )

        # Average available GPS coordinates from unique reports.
        latitudes = []
        longitudes = []

        for report in unique_reports:
            latitude = get_value(report, "latitude")
            longitude = get_value(report, "longitude")

            if latitude is not None and longitude is not None:
                latitudes.append(float(latitude))
                longitudes.append(float(longitude))

        latitude = (
            sum(latitudes) / len(latitudes)
            if latitudes
            else None
        )

        longitude = (
            sum(longitudes) / len(longitudes)
            if longitudes
            else None
        )

        # Collect distinct sources.
        sources = sorted({
            get_value(report, "source", "Unknown") or "Unknown"
            for report in submitted_reports
        })

        # Routine weather conditions are observations, not active events.
        if event_type.casefold() in OBSERVATION_TYPES:
            event_status = "OBSERVATION"
        else:
            event_status = "ACTIVE"

        # Preserve the existing event ID naming convention.
        event_id = (
            f"{city.upper()}-"
            f"{event_type.upper().replace(' ', '-')}"
        )

        events.append({
            "event_id": event_id,
            "city": city,
            "state": state,
            "event_type": event_type,
            "report_count": report_count,
            "submitted_report_count": submitted_report_count,
            "duplicate_count": duplicate_count,
            "near_duplicate_count": near_duplicate_count,
            "near_duplicate_pairs": near_duplicate_pairs,
            "verified_report_count": verification_counts["verified"],
            "pending_report_count": verification_counts["pending"],
            "under_review_report_count": verification_counts["under_review"],
            "rejected_report_count": verification_counts["rejected"],
            "confidence": confidence,
            "latitude": (
                round(latitude, 6) if latitude is not None else None
            ),
            "longitude": (
                round(longitude, 6) if longitude is not None else None
            ),
            "sources": sources,
            "status": event_status,
        })

    return {
        "total_events": len(events),
        "events": events,
    }
