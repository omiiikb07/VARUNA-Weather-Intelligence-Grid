
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Literal

from database import engine, get_db
from models import Base, WeatherReport
from ai_engine import analyze_report
from event_engine import create_event_summary
from ingestion.source_manager import collect_weather
from fastapi.middleware.cors import CORSMiddleware


# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="VARUNA",
    description="National Weather Intelligence & Verification Grid",
    version="1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


class VerificationUpdate(BaseModel):
    status: Literal["Verified", "Rejected", "Under Review"]


def parse_observed_at(value):
    """Convert an ISO observation timestamp to naive UTC for SQLite."""
    if not value:
        return None

    if isinstance(value, datetime):
        observed = value
    else:
        observed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    if observed.tzinfo is not None:
        observed = observed.astimezone(timezone.utc).replace(tzinfo=None)

    return observed


@app.get("/")
def home():
    return {
        "project": "VARUNA",
        "message": "National Weather Intelligence Grid is running",
        "status": "online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/reports")
def get_reports(db: Session = Depends(get_db)):
    reports = db.query(WeatherReport).all()
    return reports


@app.post("/reports")
def create_report(
    report: dict,
    db: Session = Depends(get_db)
):
    text = report["text"]
    source = report["source"]

    analysis = analyze_report(text, source)

    new_report = WeatherReport(
        text=text,
        city=report["city"],
        state=report["state"],
        latitude=report.get("latitude"),
        longitude=report.get("longitude"),
        source=source,
        event_type=analysis["event_type"],
        trust_score=analysis["trust_score"],
        verification_status="Pending"
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "report": new_report,
        "ai_analysis": analysis
    }


@app.post("/ingestion/weather")
def ingest_weather(db: Session = Depends(get_db)):
    """
    Collect current weather, preprocess reports,
    analyze them, and store them in the database.
    """

    collection = collect_weather()

    errors = list(collection["errors"])
    inserted_reports = []
    skipped = 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(minutes=15)

    try:
        for report in collection["reports"]:
            city = report["city"]
            state = report["state"]
            text = report["text"]
            source = report["source"]

            existing = db.query(WeatherReport).filter(
                WeatherReport.city == city,
                WeatherReport.state == state,
                WeatherReport.source == source,
                WeatherReport.text == text,
                WeatherReport.timestamp >= cutoff
            ).first()

            if existing:
                skipped += 1
                continue

            try:
                analysis = analyze_report(text, source)

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

                    # Newly added structured weather fields
                    weather_data=report.get("weather_data"),
                    observed_at=parse_observed_at(
                        report.get("observed_at")
                    )
                )

                db.add(new_report)
                db.flush()

                inserted_reports.append({
                    "id": new_report.id,
                    "city": new_report.city,
                    "state": new_report.state,
                    "event_type": new_report.event_type,
                    "trust_score": new_report.trust_score,
                    "verification_status": new_report.verification_status,
                    "observed_at": (
                        new_report.observed_at.isoformat()
                        if new_report.observed_at else None
                    )
                })

            except Exception as error:
                errors.append({
                    "city": city,
                    "state": state,
                    "error": str(error)
                })

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save collected weather reports"
        )

    return {
        "message": "Weather ingestion completed",
        "collected_at": collection["collected_at"],
        "total_locations": collection["total_locations"],
        "collected": collection["successful"],
        "inserted": len(inserted_reports),
        "skipped_duplicates": skipped,
        "failed": len(errors),
        "reports": inserted_reports,
        "errors": errors
    }


@app.patch("/reports/{report_id}/verification")
def update_verification(
    report_id: int,
    verification: VerificationUpdate,
    db: Session = Depends(get_db)
):
    report = db.query(WeatherReport).filter(
        WeatherReport.id == report_id
    ).first()

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    report.verification_status = verification.status

    db.commit()
    db.refresh(report)

    return {
        "message": "Verification status updated successfully",
        "report_id": report.id,
        "verification_status": report.verification_status
    }


@app.get("/events")
def get_events(db: Session = Depends(get_db)):
    reports = db.query(WeatherReport).all()
    return create_event_summary(reports)
