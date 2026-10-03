
from database import SessionLocal
from models import WeatherReport
from ai_engine import analyze_report

db = SessionLocal()

try:
    reports = db.query(WeatherReport).filter(
        WeatherReport.source.ilike("Weather API%"),
        WeatherReport.event_type == "Unknown"
    ).all()

    if not reports:
        print("No Unknown Open-Meteo reports found.")
    else:
        updated = 0

        for report in reports:
            analysis = analyze_report(report.text, report.source)

            old_type = report.event_type
            new_type = analysis["event_type"]

            print(
                f"ID {report.id} | {report.city}: "
                f"{old_type} -> {new_type}"
            )

            report.event_type = new_type
            report.trust_score = analysis["trust_score"]
            updated += 1

        db.commit()
        print(f"\nSuccessfully re-analyzed {updated} reports.")
        print("Verification statuses were preserved.")

except Exception as error:
    db.rollback()
    print(f"Update failed. Changes rolled back: {error}")

finally:
    db.close()
