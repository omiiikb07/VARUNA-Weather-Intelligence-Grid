from collections import defaultdict
import re


def normalize_text(text):
    """Normalize text to help identify exact duplicate reports."""
    if not text:
        return ""

    text = text.casefold().strip()
    text = re.sub(r"\s+", " ", text)

    return text


def create_event_summary(reports):
    groups = defaultdict(list)

    for report in reports:
        city = (report.city or "Unknown").strip()
        event_type = (report.event_type or "Unclassified").strip()

        key = (
            city.casefold(),
            event_type.casefold()
        )

        groups[key].append(report)

    events = []

    for (city, event_type), group in groups.items():
        unique_reports = []
        seen_reports = set()

        for index, report in enumerate(group):
            normalized = normalize_text(report.text)

            # Empty reports should not all be treated as duplicates.
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
            avg_latitude = sum(
                latitude for latitude, longitude in valid_coordinates
            ) / len(valid_coordinates)

            avg_longitude = sum(
                longitude for latitude, longitude in valid_coordinates
            ) / len(valid_coordinates)

            latitude = round(avg_latitude, 4)
            longitude = round(avg_longitude, 4)
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
            "confidence": confidence,
            "latitude": latitude,
            "longitude": longitude,
            "sources": sources,
            "status": "ACTIVE"
        })

    return events