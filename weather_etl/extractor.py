import requests
import pprint

url = "https://api.open-meteo.com/v1/forecast"

params = {
	"latitude": 35.924086,
	"longitude": -106.791974,
	"hourly": ["temperature_2m", "precipitation_probability"],
	"temperature_unit": "fahrenheit",
}

response = requests.get(url, params = params)

data = response.json()

print(data)
print("Time:", data['hourly']['time'][0] + " " + data['hourly_units']['time'])
print(str(data['hourly']['temperature_2m'][0]) + data['hourly_units']['temperature_2m'])