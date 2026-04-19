import sys
from datetime import datetime
from time import perf_counter

_t0 = perf_counter()

def _dbg(msg: str) -> None:
    print(f"[DEBUG +{perf_counter() - _t0:6.2f}s] {msg}", file=sys.stderr)

from config import MAX_ARRIVALS, MY_LAT, MY_LON, RADIUS_MILES, ROUTES
from distance import haversine_miles
from nextrip import get_departures, get_stops_near


def format_time(departure_time: int) -> str:
    dt = datetime.fromtimestamp(departure_time)
    return dt.strftime("%I:%M %p").lstrip("0")


def main():
    route_names = {route_id: name for route_id, name in ROUTES}
    route_ids = set(route_names)
    radius_meters = int(RADIUS_MILES * 1609.34)

    _dbg(f"Fetching stops within {RADIUS_MILES} mi ({radius_meters} m)...")
    try:
        nearby = get_stops_near(MY_LAT, MY_LON, radius_meters)
    except Exception as e:
        print(f"Could not fetch nearby stops: {e}", file=sys.stderr)
        return
    _dbg(f"Got {len(nearby)} nearby stop(s)")
    for stop in nearby:
        _dbg(f"  Stop {stop.get('stop_id')}: {stop.get('description')} ({stop.get('latitude')}, {stop.get('longitude')})")

    stops_by_dist = sorted(
        nearby,
        key=lambda s: haversine_miles(MY_LAT, MY_LON, s["latitude"], s["longitude"])
    )

    # For each (route_id, direction_id), collect up to MAX_ARRIVALS from the closest stop
    seen: dict[tuple, tuple] = {}  # (route_id, dir_id) -> (stop_desc, [departures])

    for stop in stops_by_dist:
        stop_id = stop["stop_id"]
        stop_desc = stop.get("description", f"Stop {stop_id}")

        _dbg(f"Fetching departures for {stop_desc} (stop {stop_id})...")
        try:
            data = get_departures(stop_id)
        except Exception as e:
            print(f"Could not fetch departures for stop {stop_id}: {e}", file=sys.stderr)
            continue
        _dbg(f"Got {len(data.get('departures', []))} departure(s)")

        for dep in data.get("departures", []):
            rid = str(dep.get("route_id"))
            did = dep.get("direction_id")
            if rid not in route_ids:
                continue
            key = (rid, did)
            if key not in seen:
                seen[key] = (stop_desc, [])
            if len(seen[key][1]) < MAX_ARRIVALS:
                seen[key][1].append(dep)

    found_any = False
    for (rid, _), (stop_desc, deps) in sorted(seen.items()):
        route_name = route_names[rid]
        for dep in deps:
            dep_time = dep.get("departure_time")
            time_str = format_time(dep_time) if dep_time else dep.get("departure_text", "unknown")
            dir_text = dep.get("direction_text", "")
            dest = dep.get("description", "")
            print(f"Route {route_name} {dir_text} toward {dest} at {stop_desc}: {time_str}")
            found_any = True

    if not found_any:
        print("No upcoming arrivals found within the search radius.")


if __name__ == "__main__":
    main()
