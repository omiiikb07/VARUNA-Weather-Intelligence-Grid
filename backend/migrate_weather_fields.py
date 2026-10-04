from sqlalchemy import inspect, text
from database import engine

table_name = "weather_reports"

existing_columns = {
    column["name"]
    for column in inspect(engine).get_columns(table_name)
}

with engine.begin() as connection:

    # Structured weather data
    if "weather_data" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN weather_data JSON"
            )
        )
        print("Added weather_data column.")
    else:
        print("weather_data column already exists.")

    # Weather observation timestamp
    if "observed_at" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN observed_at DATETIME"
            )
        )
        print("Added observed_at column.")
    else:
        print("observed_at column already exists.")

    # Automated assessment status
    if "assessment_status" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN assessment_status VARCHAR "
                "NOT NULL DEFAULT 'Uncertain'"
            )
        )
        print("Added assessment_status column.")
    else:
        print("assessment_status column already exists.")

    # Reason for automated assessment
    if "assessment_reason" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN assessment_reason TEXT"
            )
        )
        print("Added assessment_reason column.")
    else:
        print("assessment_reason column already exists.")

    # Assessment score
    if "assessment_score" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN assessment_score INTEGER"
            )
        )
        print("Added assessment_score column.")
    else:
        print("assessment_score column already exists.")

    # Assessment evidence (JSON array)
    if "assessment_evidence" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN assessment_evidence JSON"
            )
        )
        print("Added assessment_evidence column.")
    else:
        print("assessment_evidence column already exists.")

    # Assessment timestamp
    if "assessed_at" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE weather_reports "
                "ADD COLUMN assessed_at DATETIME"
            )
        )
        print("Added assessed_at column.")
    else:
        print("assessed_at column already exists.")

print("Database migration completed.")
