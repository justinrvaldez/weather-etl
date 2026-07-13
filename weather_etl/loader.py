import psycopg
import datetime
import os

from transformer import transformer
from extractor import extractor
from dotenv import load_dotenv

load_dotenv()

issue_date = datetime.datetime.now(datetime.timezone.utc)
schema_location, readings = transformer(extractor(), issue_date)

# Establish a connection to the PostgreSQL database using psycopg 3. Read as psycho-pg, was a typo when named. 
# Connection parameters are retrieved from 
# environment variables for security and flexibility. Gitignore the .env file containing 
# sensitive information like database credentials.

connection = psycopg.connect( # Initilize connection object by passing in connection arugements as keyword arguments. The connection parameters are retrieved from environment variables for security and flexibility.
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)

cursor_location = connection.cursor()

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
    DO NOTHING
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

if result is None:
    print("Location already exists.")
else:
    location_id = result[0]
    print(f"Inserted new location with ID: {location_id}")

connection.commit()
cursor_location.close()
connection.close()