
@app.post("/reports")
def create_report(
    report: dict,
    db: Session = Depends(get_db)
):
    text = report["text"]
    source = report["source"]
    city = report["city"]
    state = report["state"]

    analysis = analyze_report(text, source)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find recent, source-validated weather observations
    # for the same city and state.
    observations = (
        db.query(WeatherReport)
        .filter(
            WeatherReport.city.ilike(city),
            WeatherReport.state.ilike(state),
            WeatherReport.source == "Weather API (Open-Meteo)",
            WeatherReport.assessment_status == "Source Validated",
            WeatherReport.observed_at.isnot(None),
            WeatherReport.observed_at >= now - timedelta(hours=3),
            WeatherReport.observed_at <= now + timedelta(minutes=15)
        )
        .order_by(WeatherReport.observed_at.desc())
        .all()
    )

    assessment_status, assessment_reason = (
        assess_citizen_report(
            analysis["event_type"],
            observations
        )
    )

    new_report = WeatherReport(
        text=text,
        city=city,
        state=state,
        latitude=report.get("latitude"),
        longitude=report.get("longitude"),
        source=source,
        event_type=analysis["event_type"],
        trust_score=analysis["trust_score"],
        verification_status="Pending",
        assessment_status=assessment_status,
        assessment_reason=assessment_reason,
        assessed_at=now
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "report": new_report,
        "ai_analysis": analysis,
        "automated_assessment": {
            "status": new_report.assessment_status,
            "reason": new_report.assessment_reason,
            "assessed_at": (
                new_report.assessed_at.isoformat()
                if new_report.assessed_at else None
            )
        }
    }
