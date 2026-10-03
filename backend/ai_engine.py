import re


EVENT_KEYWORDS = {
    "Flood": [
        "flood",
        "flooded",
        "flooding",
        "waterlogging",
        "water logged",
        "water entered",
        "submerged",
        "roads underwater"
    ],

    "Heavy Rainfall": [
        "heavy rain",
        "heavy rainfall",
        "intense rain",
        "torrential rain",
        "downpour",
        "rainfall"
    ],

    "Thunderstorm": [
        "thunderstorm",
        "thunder",
        "lightning",
        "storm"
    ],

    "Heatwave": [
        "heatwave",
        "heat wave",
        "extreme heat",
        "very hot",
        "temperature high"
    ],

    "Fog": [
        "fog",
        "dense fog",
        "low visibility",
        "mist"
    ],

    "Dust Storm": [
        "dust storm",
        "dust",
        "dusty"
    ],

    "Strong Wind": [
        "strong wind",
        "high winds",
        "gust",
        "windstorm"
    ],

    "Hailstorm": [
        "hail",
        "hailstorm",
        "hailstones"
    ]
}


def classify_event(text: str):
    """
    Identify the most likely weather event
    from the report text.
    """

    text = text.lower()

    scores = {}

    for event, keywords in EVENT_KEYWORDS.items():

        score = 0

        for keyword in keywords:
            if keyword in text:
                score += 1

        scores[event] = score

    best_event = max(scores, key=scores.get)
    best_score = scores[best_event]

    if best_score == 0:
        return "Unknown", 30

    confidence = min(60 + (best_score * 12), 96)

    return best_event, confidence


def calculate_trust_score(
    text,
    source,
    event_confidence
):
    """
    Lightweight explainable trust score.
    """

    score = 40

    # Source reliability
    trusted_sources = [
        "IMD",
        "Weather API",
        "Government Dataset",
        "Official Source"
    ]

    if source in trusted_sources:
        score += 30

    elif source == "Citizen Report":
        score += 15

    elif source == "Social Media":
        score += 5

    # Event classification confidence
    score += int(event_confidence * 0.2)

    # Detailed reports get a small boost
    if len(text) > 50:
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