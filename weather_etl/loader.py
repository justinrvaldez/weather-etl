import psycopg
import datetime
import os

from transformer import transformer
from extractor import extractor
from dotenv import load_dotenv

load_dotenv()

# Forecasts from openmeteo are issued at 00:00, 06:00, 12:00, and 18:00. The ETL program will run a few minuutes 
# after each of the those updated forecasts. To avoid making duplicate rows and enforcing imdempotency, issue dates
# are zeroed and set to the nearest forecasts window.

issue_date = datetime.datetime.now(datetime.timezone.utc)
issue_date_hour = (issue_date.hour // 6) * 6
issued_window = issue_date.replace(hour=issue_date_hour, minute=0,second=0,microsecond=0)
schema_location, readings = transformer(extractor(), issued_window)

# Establish a connection to the PostgreSQL database using psycopg 3. Read as psycho-pg, was a typo when named. 
# Connection parameters are retrieved from environment variables for security and flexibility. 
# Gitignore the .env file containing sensitive information like database credentials.
# Initilize connection object by passing in connection arugements as keyword arguments. 
# The connection parameters are retrieved from environment variables for security and flexibility.

connection = psycopg.connect(
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)

# Create two cursors for executing SQL commands. One cursor is used for inserting data into the locations table,
# and the other cursor is used for inserting data into the readings table.

cursor_location = connection.cursor()
cursor_readings = connection.cursor()

# The order of the values must match the order of the columns in the
# INSERT statement. Postgresql attached each %s placeholder to the 
# corresponding value in the tuple provided as the second argument to cursor_location.execute().

cursor_location.execute(
    """
    INSERT INTO locations (
        latitude,
        longitude,
        elevation,
        timezone,
        utc_offset_seconds,
        unit_precipitation,
        unit_time,
        unit_temp
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (latitude, longitude)
    DO UPDATE SET elevation = EXCLUDED.elevation
    RETURNING location_id
    """,
    (
        schema_location["latitude"],
        schema_location["longitude"],
        schema_location["elevation"],
        schema_location["timezone"],
        schema_location["utc_offset_seconds"],
        schema_location["unit_precipitation"],
        schema_location["unit_time"],
        schema_location["unit_temp"],
    )
)

result = cursor_location.fetchone()
location_id = result[0]
print(f"Location id: {location_id}")

cursor_readings.executemany(
    """
    INSERT INTO readings (
        location_id,
        forecast_issued,
        time,
        temperature_2m,
        precipitation_probability
    )
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (location_id, time, forecast_issued) DO NOTHING
    """,
    [
        (
            location_id,
            reading["forecast_issued"],
            reading["time"],
            reading["temperature_2m"],
            reading["precipitation_probability"]
        )
        for reading in readings
    ]
)

connection.commit()

cursor_location.close()
cursor_readings.close()

connection.close()