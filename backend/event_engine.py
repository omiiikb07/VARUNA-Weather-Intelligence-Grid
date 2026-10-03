
from collections import defaultdict
from difflib import SequenceMatcher
import re


NEAR_DUPLICATE_THRESHOLD = 0.72
MIN_TEXT_LENGTH = 20


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
    text = re.sub(r"\s+", " ", text).strip()

    return text


def calculate_similarity(text1, text2):
    """Return text similarity as a percentage."""
    normalized1 = normalize_for_similarity(text1)
    normalized2 = normalize_for_similarity(text2)

    if not normalized1 or not normalized2:
        return 0

    return SequenceMatcher(
        None, normalized1, normalized2
    ).ratio()


def find_near_duplicates(reports):
    """Find potential near-duplicate pairs without removing reports."""
    potential_duplicates = []

    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            report1 = reports[i]
            report2 = reports[j]

            text1 = report1.text or ""
            text2 = report2.text or ""

            # Skip very short reports to reduce false matches.
            if (
                len(normalize_for_similarity(text1)) < MIN_TEXT_LENGTH
                or len(normalize_for_similarity(text2)) < MIN_TEXT_LENGTH
            ):
                continue

            similarity = calculate_similarity(text1, text2)

            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                potential_duplicates.append({
                    "report_id_1": report1.id,
                    "report_id_2": report2.id,
                    "similarity": round(similarity * 100, 2),
                    "status": "POTENTIAL_DUPLICATE"
                })

    return potential_duplicates


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

        # Detect near duplicates among exact-text unique reports.
        near_duplicate_pairs = find_near_duplicates(unique_reports)

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
            "near_duplicate_count": len(near_duplicate_pairs),
            "near_duplicate_pairs": near_duplicate_pairs,
            "confidence": confidence,
            "latitude": latitude,
            "longitude": longitude,
            "sources": sources,
            "status": "ACTIVE"
        })

    return events
