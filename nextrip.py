import requests

BASE_URL = "https://svc.metrotransit.org/nextrip"
TIMEOUT = 10


def get_directions(route_id: str) -> list[dict]:
    r = requests.get(f"{BASE_URL}/directions/{route_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_stops(route_id: str, direction_id: int) -> list[dict]:
    r = requests.get(f"{BASE_URL}/stops/{route_id}/{direction_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_departures(stop_id: int) -> dict:
    r = requests.get(f"{BASE_URL}/{stop_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
