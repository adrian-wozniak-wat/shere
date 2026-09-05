import sys
import requests


def get_entity_data(ha_url, token, entity_id):
    """
    Fetches the state and attributes for a specific Home Assistant entity.

    Returns:
        tuple: (state, attributes) where attributes is a dictionary,
               or (None, None) if the request fails.
    """
    url = f"{ha_url}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        state = data.get("state")
        attributes = data.get("attributes", {})

        return state, attributes

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {entity_id}: {e}", file=sys.stderr)
        return None, None