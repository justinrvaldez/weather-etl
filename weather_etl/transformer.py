from extractor import extractor
import pprint

schema_readings = [
    {
        "reading_id": None,
        "location_id": None,          # ADDED: foreign key — links each reading to its location
        "forecast_issued_date": None, # ADDED: when this forecast was made (needed for forecast-vs-actual)
        "time": None,                 # the target timestamp being forecast
        "temperature_2m": None,
        "precipitation_probability": None
    }
]

data = extractor()

precipitation_probability_length = len(data['hourly']['precipitation_probability'])
time_probability_length = len(data['hourly']['time'])
temp_probability_length = len(data['hourly']['temperature_2m'])

if not (precipitation_probability_length == time_probability_length == temp_probability_length):
    raise ValueError(
        f"Array length mismatch: precip={precipitation_probability_length}, "
        f"time={time_probability_length}, temp={temp_probability_length}"
    )

schema_location = {
    "location_id": None,
    "latitude": data["latitude"],
    "longitude": data["longitude"],
    "elevation": data["elevation"],
    "timezone": data["timezone"],
    "utc_offset_seconds": data["utc_offset_seconds"],
    "unit_precipitation": data["hourly_units"]["precipitation_probability"],
    "unit_time": data["hourly_units"]["time"],
    "unit_temp": data["hourly_units"]["temperature_2m"],
}

print(schema_location)