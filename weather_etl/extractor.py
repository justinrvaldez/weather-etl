import requests
import logging

# For recording information abouut what the program is doing.
# Logging configuration to log messages with timestamp, log level, and message content. 
# The logging level is set to INFO, which means that all messages at this level and above 
# (WARNING, ERROR, CRITICAL) will be logged.
# Levels of logging severity, in increasing order, are: DEBUG, INFO, WARNING, ERROR, CRITICAL.
# Currently set to INFO, which means that all messages at this level and above (WARNING, ERROR, CRITICAL) will be 
# logged. Change after testing to WARNING or ERROR to reduce verbosity in production.
# The format argument specifies the format of the log messages. 
# In this case, it includes the timestamp, log level, and message content. Can be changed to 
# include additional information like module name, function name, etc. if needed.

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

def extractor():

    url = "https://api.open-meteo.com/v1/forecast"

    # Parameters for the API request are defined in a dictionary. If you want to add more parameters, you 
    # can do so by adding key-value pairs to this dictionary. However this will change the schema of the data 
    # returned by the API, and will require changes to the transformer function to handle the new data 
    # structure as well as a change to the loader and SQL database schema to handle the new data structure.
    
    params = {
        "latitude": 35.824086,
        "longitude": -106.791974,
        "hourly": ["temperature_2m", "precipitation_probability"],
        "temperature_unit": "fahrenheit" # Default is Celsius. Change to Fahrenheit for US users.
    }

    # Many exceptions can be added to a try-except block to handle different 
    # types of errors that may occur during the execution of the code. Added in logging.info() 
    # to log the start of the extraction process, which can be useful for tracking
    # the program and debugging. May remove after testing to reduce verbosity.

    try:
        logging.info("Starting data extraction from Open-Meteo API...")
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

