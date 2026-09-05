import sys
import requests

# --- Configuration ---
# If running locally on the HA machine, you can use http://localhost:8123
# Do not include a trailing slash
HOME_ASSISTANT_URL = "http://192.168.1.216:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlNzMwYjdkNjM2MWQ0ZDNmYjlmMjJlOTdjYjg1NmNlMiIsImlhdCI6MTc4MDIxNjk3MywiZXhwIjoyMDk1NTc2OTczfQ.VrBuYtdiClD93ySjZ4N_3-ekvytDxwXFjwvda-rcgcQ"

# Replace these with your actual Home Assistant entity IDs
CO2_ENTITY_ID = "sensor.wifi_smart_switch_carbon_dioxide"
TEMP_ENTITY_ID = "sensor.wifi_smart_switch_temperature"
# ---------------------


def get_entity_state(entity_id: str) -> dict:
    """Fetches the full state object for a given entity ID."""
    url = f"{HOME_ASSISTANT_URL}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        # Raise an exception for 4xx or 5xx status codes
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {entity_id}: {e}", file=sys.stderr)
        return {}


def main():
    print("Fetching current sensor data from Home Assistant...")
    print("-" * 50)

    # Fetch CO2 Data
    co2_data = get_entity_state(CO2_ENTITY_ID)
    if co2_data:
        co2_state = co2_data.get("state")
        co2_unit = co2_data.get("attributes", {}).get(
            "unit_of_measurement", "ppm"
        )
        print(f"Carbon Dioxide Level: {co2_state} {co2_unit}")

    # Fetch Temperature Data
    temp_data = get_entity_state(TEMP_ENTITY_ID)
    if temp_data:
        temp_state = temp_data.get("state")
        temp_unit = temp_data.get("attributes", {}).get(
            "unit_of_measurement", "°C"
        )
        print(f"Temperature:          {temp_state} {temp_unit}")


if __name__ == "__main__":
    main()