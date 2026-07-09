from extractor import extractor
import pprint
import datetime

data = extractor()

issue_date = datetime.datetime.now(datetime.timezone.utc)

def transformer(extracted_data, date):
    precipitation_probability_length = len(extracted_data['hourly']['precipitation_probability'])
    time_probability_length = len(extracted_data['hourly']['time'])
    temp_probability_length = len(extracted_data['hourly']['temperature_2m'])

    if not (precipitation_probability_length == time_probability_length == temp_probability_length):
        raise ValueError(
            f"Array length mismatch: precip={precipitation_probability_length}, "
            f"time={time_probability_length}, temp={temp_probability_length}"
        )

    schema_location = {
        "location_id": None,
        "latitude": extracted_data["latitude"],
        "longitude": extracted_data["longitude"],
        "elevation": extracted_data["elevation"],
        "timezone": extracted_data["timezone"],
        "utc_offset_seconds": extracted_data["utc_offset_seconds"],
        "unit_precipitation": extracted_data["hourly_units"]["precipitation_probability"],
        "unit_time": extracted_data["hourly_units"]["time"],
        "unit_temp": extracted_data["hourly_units"]["temperature_2m"],
    }

    print(schema_location)
    readings = []
    for i in range(precipitation_probability_length):
        readings.append({
            "reading_id": None,  # Assuming reading_id starts from 1
            "location_id": None,     # Assuming a single location with ID 1 for this example
            "forecast_issued": date,  # Assuming current weather time as forecast issued date
            "time": extracted_data['hourly']['time'][i],
            "temperature_2m": extracted_data['hourly']['temperature_2m'][i],
            "precipitation_probability": extracted_data['hourly']['precipitation_probability'][i]
        })
        
    return schema_location, readings # Return order matters for consistency, schema_location first, readings second

pprint.pprint(transformer(data, issue_date))