import requests

BASE_URL = "https://svc.metrotransit.org/nextrip"
TIMEOUT = 10


def get_stops_near(lat: float, lon: float, radius_meters: int) -> list[dict]:
    r = requests.get(f"{BASE_URL}/stops", params={"lat": lat, "lon": lon, "radius": radius_meters}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_departures(stop_id: int) -> dict:
    r = requests.get(f"{BASE_URL}/{stop_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
