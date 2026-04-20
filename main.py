import sys
from datetime import datetime
from time import perf_counter

_t0 = perf_counter()

def _dbg(msg: str) -> None:
    print(f"[DEBUG +{perf_counter() - _t0:6.2f}s] {msg}", file=sys.stderr)

from config import MAX_ARRIVALS, MY_LAT, MY_LON, RADIUS_MILES, ROUTES
from distance import haversine_miles
from nextrip import get_departures, get_directions, get_routes, get_stops


def format_time(departure_time: int) -> str:
    dt = datetime.fromtimestamp(departure_time)
    return dt.strftime("%I:%M %p").lstrip("0")


def main():
    # TODO: config.py ROUTES should distinguish weekday / Saturday / Sunday+holiday
    # availability, since some routes run on reduced schedules or not at all.
    _dbg("Fetching active routes...")
    try:
        all_routes = get_routes()
    except Exception as e:
        print(f"Could not fetch routes: {e}", file=sys.stderr)
        return
    active_ids = {r["route_id"] for r in all_routes}
    routes_to_check = [(rid, name) for rid, name in ROUTES if rid in active_ids]
    missing = [name for rid, name in ROUTES if rid not in active_ids]
    if missing:
        print(f"Skipping routes not active today: {', '.join(missing)}", file=sys.stderr)
    _dbg(f"Checking {len(routes_to_check)} active route(s)")

    found_any = False

    for route_id, route_name in routes_to_check:
        _dbg(f"Fetching directions for {route_name}...")
        try:
            directions = get_directions(route_id)
        except Exception as e:
            print(f"[{route_name}] Could not fetch directions: {e}", file=sys.stderr)
            continue
        _dbg(f"Got {len(directions)} direction(s)")

        for direction in directions:
            dir_id = direction["direction_id"]
            dir_name = direction["direction_name"]

            _dbg(f"Fetching stops for {route_name} {dir_name}...")
            try:
                stops = get_stops(route_id, dir_id)
            except Exception as e:
                print(f"[{route_name} {dir_name}] Could not fetch stops: {e}", file=sys.stderr)
                continue
            _dbg(f"Got {len(stops)} stop(s)")

            nearest_stop = None
            nearest_dist = float("inf")
            nearest_deps = []

            for stop_info in stops:
                place_code = stop_info["place_code"]
                place_desc = stop_info.get("description", place_code)
                _dbg(f"  Fetching departures for {place_desc} ({place_code})...")
                try:
                    data = get_departures(route_id, dir_id, place_code)
                except Exception as e:
                    print(f"[{route_name} {dir_name} {place_code}] Could not fetch departures: {e}", file=sys.stderr)
                    continue

                stop = data["stops"][0] if data.get("stops") else None
                if not stop:
                    continue
                lat, lon = stop.get("latitude"), stop.get("longitude")
                if lat is None or lon is None:
                    continue

                dist = haversine_miles(MY_LAT, MY_LON, lat, lon)
                _dbg(f"    {place_desc}: {dist:.3f} mi away")
                if dist <= RADIUS_MILES and dist < nearest_dist:
                    nearest_stop = stop
                    nearest_dist = dist
                    nearest_deps = data.get("departures", [])[:MAX_ARRIVALS]

            if nearest_stop is None:
                _dbg(f"No stops within radius for {route_name} {dir_name}")
                continue

            stop_desc = nearest_stop.get("description", f"Stop {nearest_stop.get('stop_id')}")
            _dbg(f"Nearest: {stop_desc} ({nearest_dist:.3f} mi), {len(nearest_deps)} departure(s)")

            for dep in nearest_deps:
                dep_time = dep.get("departure_time")
                time_str = format_time(dep_time) if dep_time else dep.get("departure_text", "unknown")
                dir_text = dep.get("direction_text", dir_name)
                dest = dep.get("description", "")
                print(f"Route {route_name} {dir_text} toward {dest} at {stop_desc}: {time_str}")
                found_any = True

    if not found_any:
        print("No upcoming arrivals found within the search radius.")


if __name__ == "__main__":
    main()
