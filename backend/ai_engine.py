
import re


# Severe weather event keywords with weighted scores.
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


# Routine weather conditions.
OBSERVATION_KEYWORDS = {
    "Clear Sky": [
        "clear sky",
        "clear skies",
    ],
    "Mainly Clear": [
        "mainly clear",
        "mostly clear",
    ],
    "Partly Cloudy": [
        "partly cloudy",
        "partly clouded",
    ],
    "Overcast": [
        "overcast",
    ],
    "Light Rain": [
        "light rain",
        "light rainfall",
        "drizzle",
    ],
    "Moderate Rain": [
        "moderate rain",
        "moderate rainfall",
    ],
    "Snow": [
        "snowfall",
        "snow",
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for consistent keyword matching."""
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_event(text: str):
    """
    Classify severe weather events and routine weather
    observations using weighted keyword matching.

    This is a rule-based heuristic classifier.
    Confidence is a heuristic score, not a probability.
    """
    normalized = normalize_text(text)

    if not normalized:
        return "Unknown", 30

    scores = {}

    # Score each severe weather event.
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

        # Prefer longer phrases to avoid counting
        # overlapping phrases more than once.
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

    # Resolve ties when multiple event types have
    # the same highest score.
    if best_score > 0 and best_score == second_score:
        tied_events = [
            event for event, score in ranked
            if score == best_score
        ]

        # Give Flood priority when there is a clear
        # flooding indicator.
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
            return "Flood", 75

        # Priority order for tied event classifications.
        priority = [
            "Thunderstorm",
            "Heavy Rainfall",
            "Strong Wind",
            "Hailstorm",
            "Heatwave",
            "Fog",
            "Dust Storm",
            "Flood",
        ]

        for event in priority:
            if event in tied_events:
                return event, 70

    # Strong severe-weather matches take priority
    # over routine weather observations.
    if best_score >= 3:
        score_gap = best_score - second_score

        confidence = min(
            55
            + min(best_score * 5, 25)
            + min(score_gap * 3, 12),
            92
        )

        return best_event, confidence

    # Classify routine weather conditions if no
    # strong severe-weather event was detected.
    for condition, keywords in OBSERVATION_KEYWORDS.items():
        for keyword in keywords:
            pattern = (
                r"(?<!\w)"
                + re.escape(keyword)
                + r"(?!\w)"
            )

            if re.search(pattern, normalized):
                return condition, 75

    # Weak generic keywords are not enough to
    # classify a severe weather event.
    return "Unknown", 30


def calculate_trust_score(text, source, event_confidence):
    """
    Calculate a lightweight heuristic trust score.

    This does not independently verify the source
    or the factual accuracy of a report.
    """
    score = 40

    normalized_source = (source or "").strip().casefold()

    trusted_sources = {
        "imd",
        "weather api",
        "government dataset",
        "official source",
    }

    if (
        normalized_source in trusted_sources
        or normalized_source.startswith("weather api")
    ):
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
    """
    Analyze a weather report and return its event type,
    heuristic confidence and heuristic trust score.
    """
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
