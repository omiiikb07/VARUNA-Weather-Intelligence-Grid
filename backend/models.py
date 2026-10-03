
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime, timezone

from database import Base


class WeatherReport(Base):
    __tablename__ = "weather_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Report details
    text = Column(Text, nullable=False)

    # Location
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Source and classification
    source = Column(String, nullable=False)
    event_type = Column(String, default="Unknown")

    # Trust and verification
    trust_score = Column(Float, default=0)
    verification_status = Column(
        String,
        default="Pending"
    )

    # Report submission time (UTC)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
