from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime

from database import Base


class WeatherReport(Base):
    __tablename__ = "weather_reports"

    id = Column(Integer, primary_key=True, index=True)

    text = Column(Text, nullable=False)

    city = Column(String, nullable=False)
    state = Column(String, nullable=False)

    latitude = Column(Float)
    longitude = Column(Float)

    source = Column(String, nullable=False)

    event_type = Column(String, default="Unknown")

    trust_score = Column(Float, default=0)

    verification_status = Column(
        String,
        default="Pending"
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow
    )