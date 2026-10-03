
from collections import defaultdict
from difflib import SequenceMatcher
from math import radians, sin, cos, sqrt, atan2
from datetime import timezone
import re


NEAR_DUPLICATE_THRESHOLD = 0.72
MIN_TEXT_LENGTH = 20
MAX_TIME_HOURS = 6
MAX_DISTANCE_KM = 10


def normalize_text(text):
    """Normalize text to identify exact duplicate reports."""
    if not text:
        return ""

    text = text.casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_for_similarity(text):
    """Normalize text for near-duplicate comparison."""
    if not text:
        return ""

    text = text.casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def calculate_similarity(text1, text2):
    """Return text similarity as a value between 0 and 1."""
    normalized1 = normalize_for_similarity(text1)
    normalized2 = normalize_for_similarity(text2)

    if not normalized1 or not normalized2:
        return 0

    return SequenceMatcher(
        None, normalized1, normalized2
    ).ratio()


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometres."""
    earth_radius = 6371

    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius * c


def find_near_duplicates(reports):
    """Flag potential duplicates using text, time and location."""
    potential_duplicates = []

    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            report1 = reports[i]
            report2 = reports[j]

            text1 = report1.text or ""
            text2 = report2.text or ""

            normalized1 = normalize_for_similarity(text1)
            normalized2 = normalize_for_similarity(text2)

            if (
                len(normalized1) < MIN_TEXT_LENGTH
                or len(normalized2) < MIN_TEXT_LENGTH
            ):
                continue

            # Require compatible states when both are present.
            state1 = (report1.state or "").strip().casefold()
            state2 = (report2.state or "").strip().casefold()

            if state1 and state2 and state1 != state2:
                continue

            similarity = calculate_similarity(text1, text2)

            if similarity < NEAR_DUPLICATE_THRESHOLD:
                continue

            # Compare timestamps if both are available.
            time_difference_minutes = None
            timestamp1 = report1.timestamp
            timestamp2 = report2.timestamp

            if timestamp1 and timestamp2:
                if timestamp1.tzinfo is not None:
                    timestamp1 = timestamp1.astimezone(
                        timezone.utc
                    ).replace(tzinfo=None)

                if timestamp2.tzinfo is not None:
                    timestamp2 = timestamp2.astimezone(
                        timezone.utc
                    ).replace(tzinfo=None)

                time_difference_minutes = abs(
                    (timestamp1 - timestamp2).total_seconds()
                ) / 60

                if time_difference_minutes > MAX_TIME_HOURS * 60:
                    continue

            # Compare coordinates if both reports have GPS data.
            distance_km = None

            coords1 = (report1.latitude, report1.longitude)
            coords2 = (report2.latitude, report2.longitude)

            if all(value is not None for value in coords1 + coords2):
                distance_km = calculate_distance_km(
                    coords1[0], coords1[1],
                    coords2[0], coords2[1]
                )

                if distance_km > MAX_DISTANCE_KM:
                    continue

            context_complete = (
                time_difference_minutes is not None
                and distance_km is not None
            )

            potential_duplicates.append({
                "report_id_1": report1.id,
                "report_id_2": report2.id,
                "similarity": round(similarity * 100, 2),
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
                "context_status": (
                    "COMPLETE" if context_complete else "PARTIAL"
                ),
                "status": "POTENTIAL_DUPLICATE"
            })

    return potential_duplicates


def create_event_summary(reports):
    groups = defaultdict(list)

    for report in reports:
        city = (report.city or "Unknown").strip()
        event_type = (report.event_type or "Unclassified").strip()

        key = (city.casefold(), event_type.casefold())
        groups[key].append(report)

    events = []

    for (city, event_type), group in groups.items():
        unique_reports = []
        seen_reports = set()

        for index, report in enumerate(group):
            normalized = normalize_text(report.text)

            # Keep empty reports separate.
            if not normalized:
                duplicate_key = f"empty-{report.id or index}"
            else:
                duplicate_key = normalized

            if duplicate_key not in seen_reports:
                seen_reports.add(duplicate_key)
                unique_reports.append(report)

        submitted_report_count = len(group)
        report_count = len(unique_reports)
        duplicate_count = submitted_report_count - report_count

        # Detect near duplicates without removing the reports.
        near_duplicate_pairs = find_near_duplicates(
            unique_reports
        )

        avg_trust = sum(
            report.trust_score or 0
            for report in unique_reports
        ) / report_count

        valid_coordinates = [
            (report.latitude, report.longitude)
            for report in unique_reports
            if report.latitude is not None
            and report.longitude is not None
        ]

        if valid_coordinates:
            latitude = round(
                sum(lat for lat, lon in valid_coordinates)
                / len(valid_coordinates), 4
            )
            longitude = round(
                sum(lon for lat, lon in valid_coordinates)
                / len(valid_coordinates), 4
            )
        else:
            latitude = None
            longitude = None

        sources = sorted({
            report.source
            for report in unique_reports
            if report.source
        })

        confidence = min(
            int(avg_trust + min(report_count * 2, 15)),
            99
        )

        events.append({
            "event_id": (
                f"{city.upper()}-"
                f"{event_type.upper().replace(' ', '-')}"
            ),
            "city": city.title(),
            "event_type": event_type.title(),
            "report_count": report_count,
            "submitted_report_count": submitted_report_count,
            "duplicate_count": duplicate_count,
            "near_duplicate_count": len(near_duplicate_pairs),
            "near_duplicate_pairs": near_duplicate_pairs,
            "confidence": confidence,
            "latitude": latitude,
            "longitude": longitude,
            "sources": sources,
            "status": "ACTIVE"
        })

    return events
