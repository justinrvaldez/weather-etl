import psycopg
import datetime
import os

from transformer import transformer
from extractor import extractor
from dotenv import load_dotenv

load_dotenv()

# Forecasts from openmeteo are issued at 00:00, 06:00, 12:00, and 18:00. The ETL program will run a few minuutes 
# after each of the those updated forecasts. To avoid making duplicate rows and enforcing imdempotency, issue dates
# are zeroed and set to the nearest forecast_window.

def forecast_window ():
    issue_date = datetime.datetime.now(datetime.timezone.utc)
    issue_date_hour = (issue_date.hour // 6) * 6
    return issue_date.replace(hour=issue_date_hour, minute=0,second=0,microsecond=0)

def main(latitude, longitude):

    schema_location, readings = transformer(extractor(latitude, longitude), forecast_window ())

    # Establish a connection to the PostgreSQL database using psycopg 3. Read as psycho-pg, was a typo when named. 
    # Connection parameters are retrieved from environment variables for security and flexibility. 
    # Gitignore the .env file containing sensitive information like database credentials.
    # Initilize connection object by passing in connection arugements as keyword arguments. 
    # The connection parameters are retrieved from environment variables for security and flexibility.

    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    ) as connection:

        with connection.cursor() as cursor:

        # The order of the values must match the order of the columns in the
        # INSERT statement. Postgresql attached each %s placeholder to the 
        # corresponding value in the tuple provided as the second argument to cursor_location.execute().

            cursor.execute(
                """
                INSERT INTO locations (
                    latitude,
                    longitude,
                    elevation,
                    timezone,
                    utc_offset_seconds,
                    unit_time,
                    unit_temp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
                    schema_location["unit_time"],
                    schema_location["unit_temp"],
                )
            )

            result = cursor.fetchone()
            location_id = result[0]
            print(f"Location id: {location_id}")

            cursor.executemany(
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

if __name__ == "__main__":
    latitude = 30.00000
    longitude = -100.00000
    main(latitude, longitude)