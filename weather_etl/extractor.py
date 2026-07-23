import requests
import logging

def extractor(latitude, longitude):

    url = "https://api.open-meteo.com/v1/forecast"

    # Parameters for the API request are defined in a dictionary. If you want to add more parameters, you 
    # can do so by adding key-value pairs to this dictionary. However this will change the schema of the data 
    # returned by the API, and will require changes to the transformer function to handle the new data 
    # structure as well as a change to the loader and SQL database schema to handle the new data structure.
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["temperature_2m", "precipitation_probability"],
        "temperature_unit": "fahrenheit" # Default is Celsius. Change to Fahrenheit for US users.
    }

    # Many exceptions can be added to a try-except block to handle different 
    # types of errors that may occur during the execution of the code. Added in logging.info() 
    # to log the start of the extraction process, which can be useful for tracking
    # the program and debugging. May remove after testing to reduce verbosity.

    try:
        logging.info("Starting forcasted data extraction from Open-Meteo API...")
        response = requests.get(url, params = params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    
    # Handle exceptions that may occur during the HTTP request, such as connection errors or invalid responses.
    # The requests.exceptions.RequestException is a base class for all exceptions raised by the requests library. 
    # If you want to handle specific exceptions, you can catch them individually 
    # (e.g., requests.exceptions.Timeout, requests.exceptions.ConnectionError, etc.) for more granular error handling.

    except requests.exceptions.RequestException as e:
        logging.error(f"Extraction failed: {e}")
        raise

def extractor_actual(latitude, longitude, start_date, end_date):

    url = "https://archive-api.open-meteo.com/v1/archive"

    # Parameters for the API request are defined in a dictionary. If you want to add more parameters, you 
    # can do so by adding key-value pairs to this dictionary. However this will change the schema of the data 
    # returned by the API, and will require changes to the transformer function to handle the new data 
    # structure as well as a change to the loader and SQL database schema to handle the new data structure.
    # changing preciption_probablity --> precipitation in this extractor. Actual readinging do not have a probablity assigned
    # This is a real life measurement and not a guess. This is an example of assymetry between datasets.
    
    params_actual = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["temperature_2m", "precipitation"],
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "start_date": start_date,
	    "end_date": end_date
    }

    # Many exceptions can be added to a try-except block to handle different 
    # types of errors that may occur during the execution of the code. Added in logging.info() 
    # to log the start of the extraction process, which can be useful for tracking
    # the program and debugging. May remove after testing to reduce verbosity.

    try:
        logging.info("Starting archived data extraction from Open-Meteo API......")
        response = requests.get(url, params = params_actual, timeout=10)
        response.raise_for_status()
        data_actual = response.json()
        return data_actual
    
    # Handle exceptions that may occur during the HTTP request, such as connection errors or invalid responses.
    # The requests.exceptions.RequestException is a base class for all exceptions raised by the requests library. 
    # If you want to handle specific exceptions, you can catch them individually 
    # (e.g., requests.exceptions.Timeout, requests.exceptions.ConnectionError, etc.) for more granular error handling.

    except requests.exceptions.RequestException as e:
        logging.error(f"Extraction failed: {e}")
        raise

if __name__ == "__main__":

    import pprint # imported here so that it only runs in script

    print("TESTING...")

    # Testing config to view output structure.

    lat = 36.00000
    long = -100.00000
    start = "2026-07-11"
    end = "2026-07-11"

    pprint.pprint(extractor_actual(lat, long, start, end))