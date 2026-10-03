
from sqlalchemy import inspect, text
from database import engine

table_name = "weather_reports"

existing_columns = {
    column["name"]
    for column in inspect(engine).get_columns(table_name)
}

with engine.begin() as connection:
    if "weather_data" not in existing_columns:
        connection.execute(
            text("ALTER TABLE weather_reports ADD COLUMN weather_data JSON")
        )
        print("Added weather_data column.")
    else:
        print("weather_data column already exists.")

    if "observed_at" not in existing_columns:
        connection.execute(
            text("ALTER TABLE weather_reports ADD COLUMN observed_at DATETIME")
        )
        print("Added observed_at column.")
    else:
        print("observed_at column already exists.")

print("Database migration completed.")
