import sys
from datetime import datetime
from time import perf_counter

_t0 = perf_counter()

def _dbg(msg: str) -> None:
    print(f"[DEBUG +{perf_counter() - _t0:6.2f}s] {msg}", file=sys.stderr)

from config import MAX_ARRIVALS, MY_LAT, MY_LON, RADIUS_MILES, ROUTES
from distance import haversine_miles
from nextrip import get_departures, get_directions, get_stops


def format_time(departure_time: int) -> str:
    dt = datetime.fromtimestamp(departure_time)
    return dt.strftime("%I:%M %p").lstrip("0")


def main():
    found_any = False

    for route_id, route_name in ROUTES:
        _dbg(f"Fetching directions for {route_name}...")
        try:
            directions = get_directions(route_id)
        except Exception as e:
            print(f"[{route_name}] Could not fetch directions: {e}", file=sys.stderr)
            continue
        _dbg(f"Got {len(directions)} direction(s) for {route_name}")

        for direction in directions:
            dir_id = direction["direction_id"]
            dir_name = direction["direction_name"]

            _dbg(f"Fetching stops for {route_name} {dir_name}...")
            try:
                stops = get_stops(route_id, dir_id)
            except Exception as e:
                print(f"[{route_name} {dir_name}] Could not fetch stops: {e}", file=sys.stderr)
                continue
            _dbg(f"Got {len(stops)} stop(s), scanning for nearest within {RADIUS_MILES} mi...")

            nearest = None
            nearest_dist = float("inf")
            for stop in stops:
                lat = stop.get("latitude")
                lon = stop.get("longitude")
                if lat is None or lon is None:
                    continue
                dist = haversine_miles(MY_LAT, MY_LON, lat, lon)
                if dist <= RADIUS_MILES and dist < nearest_dist:
                    nearest = stop
                    nearest_dist = dist

            if nearest is None:
                _dbg(f"No stops within radius for {route_name} {dir_name}")
                continue
            _dbg(f"Nearest stop: {nearest.get('description')} ({nearest_dist:.3f} mi)")

            stop_id = nearest["stop_id"]
            stop_desc = nearest.get("description", f"Stop {stop_id}")

            _dbg(f"Fetching departures for stop {stop_id}...")
            try:
                data = get_departures(stop_id)
            except Exception as e:
                print(f"[{route_name} {dir_name}] Could not fetch departures: {e}", file=sys.stderr)
                continue
            _dbg(f"Got {len(data.get('departures', []))} departure(s) at stop")

            departures = [
                d for d in data.get("departures", [])
                if str(d.get("route_id")) == str(route_id)
            ][:MAX_ARRIVALS]

            for dep in departures:
                dep_time = dep.get("departure_time")
                time_str = format_time(dep_time) if dep_time else dep.get("departure_text", "unknown")
                print(f"Route {route_name} going {dir_name} at {stop_desc} will be arriving at {time_str}")
                found_any = True

    if not found_any:
        print("No upcoming arrivals found within the search radius.")


if __name__ == "__main__":
    main()
