from collections import defaultdict


def create_event_summary(reports):
    groups = defaultdict(list)

    for report in reports:
        key = (
            report.city.lower(),
            report.event_type.lower()
        )

        groups[key].append(report)

    events = []

    for (city, event_type), group in groups.items():

        report_count = len(group)

        avg_trust = sum(
            r.trust_score for r in group
        ) / report_count

        avg_latitude = sum(
            r.latitude or 0 for r in group
        ) / report_count

        avg_longitude = sum(
            r.longitude or 0 for r in group
        ) / report_count

        sources = list(set(
            r.source for r in group
        ))

        confidence = min(
            int(avg_trust + min(report_count * 2, 15)),
            99
        )

        events.append({
            "event_id": f"{city.upper()}-{event_type.upper().replace(' ', '-')}",
            "city": city.title(),
            "event_type": event_type.title(),
            "report_count": report_count,
            "confidence": confidence,
            "latitude": round(avg_latitude, 4),
            "longitude": round(avg_longitude, 4),
            "sources": sources,
            "status": "ACTIVE"
        })

    return events