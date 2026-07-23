import psycopg
import datetime as dt
import os
import logging


from transformer import transformer, transformer_actual
from extractor import extractor, extractor_actual
from dotenv import load_dotenv
from config import ARCHIVE_LAG_DAYS, LOCATIONS
from pathlib import Path

load_dotenv()

# For recording information abouut what the program is doing.
# Logging configuration to log messages with timestamp, log level, and message content. 
# The logging level is set to INFO, which means that all messages at this level and above 
# (WARNING, ERROR, CRITICAL) will be logged.
# Levels of logging severity, in increasing order, are: INFO, INFO, WARNING, ERROR, CRITICAL.
# Currently set to INFO, which means that all messages at this level and above (INFO, WARNING, ERROR, CRITICAL) will be 
# logged. Change after testing to WARNING or ERROR to reduce verbosity in production.
# The format argument specifies the format of the log messages. 
# In this case, it includes the timestamp, log level, and message content. Can be changed to 

LOG_PATH = Path(__file__).parent.parent / "weather_etl.log"# include additional information like module name, function name, etc. if needed.

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Forecasts from openmeteo are issued at 00:00, 06:00, 12:00, and 18:00. The ETL program will run a few minuutes 
# after each of the those updated forecasts. To avoid making duplicate rows and enforcing imdempotency, issue dates
# are zeroed and set to the nearest forecast_window.

def forecast_window ():
    issue_date = dt.datetime.now(dt.timezone.utc)
    issue_date_hour = (issue_date.hour // 6) * 6
    return issue_date.replace(hour=issue_date_hour, minute=0,second=0,microsecond=0)

def actual_window(lag):
    shift = dt.timedelta(days=lag)
    issue_date = dt.datetime.now(dt.timezone.utc)
    window = issue_date-shift
    day = window.date().isoformat()
    return day

def main(latitude, longitude):

    # the variable actual_location is not used and will be redundant for this etl in its current state. 
    # Imdepotency will handle any conflict.
    
    date_actual = actual_window(ARCHIVE_LAG_DAYS)
    schema_location, readings = transformer(extractor(latitude, longitude), forecast_window ())
    actual_location, actual_readings = transformer_actual(extractor_actual(latitude, longitude, date_actual, date_actual))

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

            # Locations
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
            logging.info(f"Location id: {location_id}")

            # Readings
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

            # Actual
            cursor.executemany(
                """
                INSERT INTO actuals (
                    location_id,
                    time,
                    temperature_2m,
                    precipitation
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (location_id, time) DO NOTHING
                """,
                [
                    (
                        location_id,
                        actual_reading["time"],
                        actual_reading["temperature_2m"],
                        actual_reading["precipitation"]
                    )
                    for actual_reading in actual_readings
                ]
            )

            connection.commit()

if __name__ == "__main__":
    try:
        logging.info("Pipeline run starting")
        latitude = LOCATIONS[0]["latitude"]
        longitude = LOCATIONS[0]["longitude"]
        main(latitude, longitude)
    except Exception as e:
        logging.exception(f"Extraction failed: {e}")
        raise

    logging.info("Pipeline run completed.")