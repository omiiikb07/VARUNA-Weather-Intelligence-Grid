from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from database import engine, get_db
from models import Base, WeatherReport
from ai_engine import analyze_report
from event_engine import create_event_summary



# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="VARUNA",
    description="National Weather Intelligence & Verification Grid",
    version="1.0"
)


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
        "timestamp": datetime.now().isoformat()
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

    # AI analysis
    analysis = analyze_report(
        text,
        source
    )

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
@app.get("/events")
def get_events(db: Session = Depends(get_db)):

    reports = db.query(WeatherReport).all()

    events = create_event_summary(reports)

    return {
        "total_events": len(events),
        "events": events
    }