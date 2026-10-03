
import re


EVENT_KEYWORDS = {
    "Flood": [
        ("roads underwater", 5),
        ("water entered", 5),
        ("waterlogging", 5),
        ("water logged", 5),
        ("submerged", 5),
        ("flooding", 5),
        ("flooded", 5),
        ("flood", 5),
    ],
    "Heavy Rainfall": [
        ("torrential rain", 5),
        ("heavy rainfall", 5),
        ("intense rain", 4),
        ("heavy rain", 4),
        ("downpour", 4),
        ("rainfall", 2),
        ("rain", 1),
    ],
    "Thunderstorm": [
        ("thunderstorm", 5),
        ("lightning", 4),
        ("thunder", 3),
        ("storm", 1),
    ],
    "Heatwave": [
        ("extreme heat", 5),
        ("heatwave", 5),
        ("heat wave", 5),
        ("very hot", 3),
        ("temperature high", 3),
    ],
    "Fog": [
        ("dense fog", 5),
        ("low visibility", 4),
        ("fog", 3),
        ("mist", 2),
    ],
    "Dust Storm": [
        ("dust storm", 5),
        ("dusty", 2),
        ("dust", 1),
    ],
    "Strong Wind": [
        ("strong winds", 5),
        ("strong wind", 5),
        ("high winds", 5),
        ("windstorm", 5),
        ("gust", 3),
    ],
    "Hailstorm": [
        ("hailstorm", 5),
        ("hailstones", 5),
        ("hail", 4),
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for consistent keyword matching."""
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_event(text: str):
    """
    Classify a weather report using weighted keywords.
    This is a heuristic classifier, not a trained ML model.
    """
    normalized = normalize_text(text)

    if not normalized:
        return "Unknown", 30

    scores = {}

    for event, keywords in EVENT_KEYWORDS.items():
        matches = []

        for keyword, weight in keywords:
            pattern = (
                r"(?<!\w)"
                + re.escape(keyword)
                + r"(?!\w)"
            )

            match = re.search(pattern, normalized)

            if match:
                matches.append(
                    (match.start(), match.end(), weight)
                )

        # Prefer longer phrases to avoid counting a phrase
        # and its contained word separately.
        matches.sort(
            key=lambda item: item[1] - item[0],
            reverse=True
        )

        selected = []

        for start, end, weight in matches:
            overlaps = any(
                start < selected_end and end > selected_start
                for selected_start, selected_end, _ in selected
            )

            if not overlaps:
                selected.append((start, end, weight))

        scores[event] = sum(
            weight for _, _, weight in selected
        )

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_event, best_score = ranked[0]
    second_score = ranked[1][1]

    if best_score == 0:
        return "Unknown", 30

    tie_resolved = False

    # Resolve a tie in favour of Flood only when the
    # report explicitly contains a flood-related indicator.
    if best_score == second_score:
        tied_events = [
            event for event, score in ranked
            if score == best_score
        ]

        flood_indicators = [
            "flood",
            "flooded",
            "flooding",
            "waterlogging",
            "water logged",
            "water entered",
            "submerged",
            "roads underwater",
        ]

        has_flood_indicator = any(
            re.search(
                r"(?<!\w)" + re.escape(keyword) + r"(?!\w)",
                normalized
            )
            for keyword in flood_indicators
        )

        if "Flood" in tied_events and has_flood_indicator:
            best_event = "Flood"
            tie_resolved = True
        else:
            return "Unknown", 45

    score_gap = best_score - second_score

    confidence = min(
        55
        + min(best_score * 5, 25)
        + min(score_gap * 3, 12),
        92
    )

    # A rule-based tie-break is less certain than a clear match.
    if tie_resolved:
        confidence = min(confidence, 75)

    return best_event, confidence


def calculate_trust_score(text, source, event_confidence):
    """
    Lightweight heuristic trust score.
    This is not independent source verification.
    """
    score = 40

    normalized_source = (source or "").strip().casefold()

    trusted_sources = {
        "imd",
        "weather api",
        "government dataset",
        "official source",
    }

    if normalized_source in trusted_sources:
        score += 30
    elif normalized_source == "citizen report":
        score += 15
    elif normalized_source == "social media":
        score += 5

    score += int(event_confidence * 0.2)

    if len((text or "").strip()) > 50:
        score += 5

    return min(score, 100)


def analyze_report(text, source):
    event_type, confidence = classify_event(text)

    trust_score = calculate_trust_score(
        text,
        source,
        confidence
    )

    return {
        "event_type": event_type,
        "confidence": confidence,
        "trust_score": trust_score
    }
