
from fastapi import FastAPI, Depends, HTTPException
import asyncio
from contextlib import asynccontextmanager, suppress
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta, date
from pydantic import BaseModel
from typing import Literal, Optional

from database import engine, get_db, SessionLocal
from models import Base, WeatherReport
from ai_engine import analyze_report
from event_engine import create_event_summary
from ingestion.source_manager import collect_weather
from assessment_engine import (
    assess_weather_api_detailed,
    assess_citizen_report_detailed
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool


# Create database tables
Base.metadata.create_all(bind=engine)


SCHEDULE_INTERVAL_SECONDS = 60 * 60

scheduler_status = {
    "enabled": True,
    "interval_minutes": 60,
    "running": False,
    "last_started": None,
    "last_completed": None,
    "last_result": None,
    "last_error": None
}


async def scheduled_weather_collection():
    # Wait one full interval after startup before the first automatic run.
    while True:
        await asyncio.sleep(SCHEDULE_INTERVAL_SECONDS)
        scheduler_status["running"] = True
        scheduler_status["last_started"] = (
            datetime.now(timezone.utc).isoformat()
        )
        scheduler_status["last_error"] = None

        db = SessionLocal()

        try:
            result = await run_in_threadpool(
                ingest_weather,
                db=db
            )

            scheduler_status["last_result"] = {
                "message": result.get("message"),
                "inserted": result.get("inserted", 0),
                "skipped_duplicates": result.get(
                    "skipped_duplicates", 0
                ),
                "failed": result.get("failed", 0)
            }

        except Exception as error:
            scheduler_status["last_error"] = str(error)

        finally:
            db.close()
            scheduler_status["last_completed"] = (
                datetime.now(timezone.utc).isoformat()
            )
            scheduler_status["running"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(
        scheduled_weather_collection()
    )

    try:
        yield
    finally:
        scheduler_task.cancel()

        with suppress(asyncio.CancelledError):
            await scheduler_task

        scheduler_status["running"] = False


app = FastAPI(
    title="VARUNA",
    description="National Weather Intelligence & Verification Grid",
    version="1.0",
    lifespan=lifespan
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


# Automatic Ingestion Status
@app.get("/ingestion/status")
def ingestion_status():
    """Return the automatic weather collection schedule and latest run."""
    return scheduler_status


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
    source = report.get("source", "Citizen Report")
    city = report["city"]
    state = report["state"]

    # Existing event classification and trust score
    analysis = analyze_report(text, source)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find recent source-validated weather observations
    # from the same city and state.
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

    # Detailed automated assessment
    assessment = assess_citizen_report_detailed(
        analysis["event_type"],
        observations
    )

    assessment_status = assessment["status"]
    assessment_reason = assessment["reason"]
    assessment_score = assessment["score"]
    assessment_evidence = assessment["evidence"]

    new_report = WeatherReport(
        text=text,
        city=city,
        state=state,
        latitude=report.get("latitude"),
        longitude=report.get("longitude"),
        source=source,
        event_type=analysis["event_type"],
        trust_score=analysis["trust_score"],

        # Human verification remains separate
        verification_status="Pending",

        # Automated assessment
        assessment_status=assessment_status,
        assessment_reason=assessment_reason,
        assessment_score=assessment_score,
        assessment_evidence=assessment_evidence,
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
            "score": new_report.assessment_score,
            "reason": new_report.assessment_reason,
            "evidence": new_report.assessment_evidence or [],
            "assessed_at": (
                new_report.assessed_at.isoformat()
                if new_report.assessed_at
                else None
            )
        }
    }


# Collect and Store Weather Data
@app.post("/ingestion/weather")
def ingest_weather(db: Session = Depends(get_db)):
    """
    Collect current weather, assess the API data,
    analyze reports, and store them in the database.
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

            try:
                # Parse provider observation time
                observed_at = parse_observed_at(
                    report.get("observed_at")
                )

                # Check for duplicate weather snapshots
                duplicate_query = db.query(WeatherReport).filter(
                    WeatherReport.city == city,
                    WeatherReport.state == state,
                    WeatherReport.source == source,
                    WeatherReport.text == text
                )

                if observed_at is not None:
                    duplicate_query = duplicate_query.filter(
                        WeatherReport.observed_at == observed_at
                    )
                else:
                    duplicate_query = duplicate_query.filter(
                        WeatherReport.timestamp >= cutoff
                    )

                existing = duplicate_query.first()

                if existing:
                    skipped += 1
                    continue

                # Existing event classification and trust score
                analysis = analyze_report(text, source)

                # Detailed automated weather API assessment
                assessment = assess_weather_api_detailed(
                    report, observed_at
                )
                assessment_status = assessment["status"]
                assessment_reason = assessment["reason"]
                assessment_score = assessment["score"]
                assessment_evidence = assessment["evidence"]

                assessed_at = datetime.now(
                    timezone.utc
                ).replace(tzinfo=None)

                # Create database record
                new_report = WeatherReport(
                    text=text,
                    city=city,
                    state=state,
                    latitude=report.get("latitude"),
                    longitude=report.get("longitude"),
                    source=source,
                    event_type=analysis["event_type"],
                    trust_score=analysis["trust_score"],

                    # Human verification remains separate
                    verification_status="Pending",

                    # Structured weather data
                    weather_data=report.get("weather_data"),
                    observed_at=observed_at,

                    # Automated assessment
                    assessment_status=assessment_status,
                    assessment_reason=assessment_reason,
                    assessment_score=assessment_score,
                    assessment_evidence=assessment_evidence,
                    assessed_at=assessed_at
                )

                db.add(new_report)
                db.flush()

                # Include inserted report in API response
                inserted_reports.append({
                    "id": new_report.id,
                    "city": new_report.city,
                    "state": new_report.state,
                    "event_type": new_report.event_type,
                    "trust_score": new_report.trust_score,
                    "verification_status": (
                        new_report.verification_status
                    ),
                    "assessment_status": (
                        new_report.assessment_status
                    ),
                    "assessment_reason": (
                        new_report.assessment_reason
                    ),
                    "assessment_score": new_report.assessment_score,
                    "assessment_evidence": (
                        new_report.assessment_evidence or []
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


# Get Overall Analytics
@app.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    reports = db.query(WeatherReport).all()

    event_type_counts = {}
    verification_counts = {
        "Verified": 0,
        "Pending": 0,
        "Under Review": 0,
        "Rejected": 0,
    }
    city_counts = {}

    for report in reports:
        # Count reports by event type
        event_type = report.event_type or "Unknown"
        event_type_counts[event_type] = (
            event_type_counts.get(event_type, 0) + 1
        )

        # Count reports by verification status
        status = (
            report.verification_status or "Pending"
        ).strip().casefold()

        if status == "verified":
            verification_counts["Verified"] += 1
        elif status == "under review":
            verification_counts["Under Review"] += 1
        elif status == "rejected":
            verification_counts["Rejected"] += 1
        else:
            verification_counts["Pending"] += 1

        # Count reports by city and state
        city = report.city or "Unknown"
        state = report.state or "Unknown"
        location_key = (city, state)

        if location_key not in city_counts:
            city_counts[location_key] = 0

        city_counts[location_key] += 1

    # Use existing event aggregation logic
    event_summary = create_event_summary(reports)

    return {
        "total_reports": len(reports),
        "total_events": event_summary["total_events"],
        "reports_by_event_type": [
            {
                "event_type": event_type,
                "count": count
            }
            for event_type, count in sorted(
                event_type_counts.items()
            )
        ],
        "reports_by_verification_status": [
            {
                "status": status,
                "count": count
            }
            for status, count in verification_counts.items()
        ],
        "reports_by_city": [
            {
                "city": city,
                "state": state,
                "count": count
            }
            for (city, state), count in sorted(
                city_counts.items()
            )
        ],
    }
