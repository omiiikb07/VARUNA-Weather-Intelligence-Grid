
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from datetime import datetime, timezone
from database import Base


class WeatherReport(Base):
    __tablename__ = "weather_reports"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)

    city = Column(String, nullable=False)
    state = Column(String, nullable=False)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    source = Column(String, nullable=False)
    event_type = Column(String, default="Unknown")
    trust_score = Column(Float, default=0)

    verification_status = Column(String, default="Pending")

    # Original database insertion timestamp
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )

    # Structured weather data from the source API
    weather_data = Column(JSON, nullable=True)

    # Actual observation time reported by the source
    observed_at = Column(DateTime, nullable=True)
