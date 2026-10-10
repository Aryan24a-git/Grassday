import json
import urllib.request

lat, lon = 40.7128, -74.0060
url = (
    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&hourly=temperature_2m,apparent_temperature,precipitation,wind_speed_10m,cloud_cover,relative_humidity_2m,uv_index"
    "&timezone=auto&past_days=1&forecast_days=7"
)
try:
    with urllib.request.urlopen(url) as response:
        weather_data = json.loads(response.read().decode())
    with open("demo_forecast.json", "w", encoding="utf-8") as f:
        json.dump(weather_data, f, indent=2)
    print("demo_forecast.json generated successfully.")
except Exception as e:
    print("Error:", e)
