def transformer(extracted_data, issued_at ):

    # Basic length checks to ensure that the arrays in the extracted data have the same length.

    precipitation_probability_length = len(extracted_data['hourly']['precipitation_probability'])
    time_probability_length = len(extracted_data['hourly']['time'])
    temp_probability_length = len(extracted_data['hourly']['temperature_2m'])

    # Check if the lengths of the arrays in the extracted data are equal. If they are not equal, 
    # raise a ValueError with a message indicating the mismatch. 

    if not (precipitation_probability_length == time_probability_length == temp_probability_length):
        raise ValueError(
            f"Array length mismatch: precip={precipitation_probability_length}, "
            f"time={time_probability_length}, temp={temp_probability_length}"
        )

    # Location schema is defined as a dictionary with keys corresponding to the columns in the location table.
    # Location_id is set to None, as it will be auto-incremented in the database. 
    # The other keys are populated with values from the extracted_data dictionary.

    location = {
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

    # Readings schema is defined as a list of dictionaries, where each dictionary corresponds to a row in the 
    # readings table. Location_id is set to None, and will be populated with location_id from the location 
    # table after insertion. The other keys are populated with values from the extracted_data dictionary. 
    # Reading_id is set to None, as it will be auto-incremented in the database. Nothing is done with the reading_id key
    # it will exist in the table for now.

    readings = []
    for i in range(precipitation_probability_length):
        readings.append({
            "reading_id": None,
            "location_id": None,
            "forecast_issued": issued_at,  # Assuming current weather time as forecast issued issued_at 
            "time": extracted_data['hourly']['time'][i],
            "temperature_2m": extracted_data['hourly']['temperature_2m'][i],
            "precipitation_probability": extracted_data['hourly']['precipitation_probability'][i]
        })
    
    # Return order matters for consistency, location first, readings second. 

    return location, readings
