
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta, date
from pydantic import BaseModel
from typing import Literal, Optional

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


# CORS Configuration
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


# Verification Request Model
class VerificationUpdate(BaseModel):
    status: Literal["Verified", "Rejected", "Under Review"]


# Convert observation timestamp to naive UTC for SQLite
def parse_observed_at(value):
    if not value:
        return None

    if isinstance(value, datetime):
        observed = value
    else:
        observed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    if observed.tzinfo is not None:
        observed = observed.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return observed


# Home Endpoint
@app.get("/")
def home():
    return {
        "project": "VARUNA",
        "message": "National Weather Intelligence Grid is running",
        "status": "online"
    }


# Health Check Endpoint
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Get Reports with Optional Filters
@app.get("/reports")
def get_reports(
    city: Optional[str] = None,
    state: Optional[str] = None,
    event_type: Optional[str] = None,
    verification_status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(WeatherReport)

    # Validate date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date"
        )

    # Filter by city
    if city and city.strip():
        query = query.filter(
            WeatherReport.city.ilike(
                f"%{city.strip()}%"
            )
        )

    # Filter by state
    if state and state.strip():
        query = query.filter(
            WeatherReport.state.ilike(
                f"%{state.strip()}%"
            )
        )

    # Filter by event type
    if event_type and event_type.strip():
        query = query.filter(
            WeatherReport.event_type.ilike(
                f"%{event_type.strip()}%"
            )
        )

    # Filter by verification status
    if verification_status and verification_status.strip():
        query = query.filter(
            WeatherReport.verification_status.ilike(
                verification_status.strip()
            )
        )

    # Filter by start date (inclusive)
    if start_date:
        start_datetime = datetime.combine(
            start_date,
            datetime.min.time()
        )

        query = query.filter(
            WeatherReport.timestamp >= start_datetime
        )

    # Filter by end date (inclusive)
    if end_date:
        end_datetime = datetime.combine(
            end_date + timedelta(days=1),
            datetime.min.time()
        )

        query = query.filter(
            WeatherReport.timestamp < end_datetime
        )

    # Newest reports first
    reports = query.order_by(
        WeatherReport.timestamp.desc()
    ).all()

    return reports


# Create Citizen or Social Media Report
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


# Collect and Store Weather Data
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

            # Check for recent duplicates
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

                    # Structured weather data
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
                    "verification_status": (
                        new_report.verification_status
                    ),
                    "observed_at": (
                        new_report.observed_at.isoformat()
                        if new_report.observed_at
                        else None
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


# Update Report Verification Status
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



# Get Event Summary with Optional Filters
@app.get("/events")
def get_events(
    city: Optional[str] = None,
    state: Optional[str] = None,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(WeatherReport)

    # Filter by city
    if city and city.strip():
        query = query.filter(
            WeatherReport.city.ilike(f"%{city.strip()}%")
        )

    # Filter by state
    if state and state.strip():
        query = query.filter(
            WeatherReport.state.ilike(f"%{state.strip()}%")
        )

    # Filter by event type
    if event_type and event_type.strip():
        query = query.filter(
            WeatherReport.event_type.ilike(f"%{event_type.strip()}%")
        )

    reports = query.order_by(
        WeatherReport.timestamp.desc()
    ).all()

    return create_event_summary(reports)
