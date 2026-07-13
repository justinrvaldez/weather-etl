import requests
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def extractor():

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": 35.824086,
        "longitude": -106.791974,
        "hourly": ["temperature_2m", "precipitation_probability"],
        "temperature_unit": "fahrenheit",
    }

    try:
        response = requests.get(url, params = params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Extraction failed: {e}")
        raise 
