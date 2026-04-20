import sys
import db
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


def populate_cache(conn: db.sqlite3.Connection) -> None:
    route_ids = {rid for rid, _ in ROUTES}

    _dbg("Populating cache: fetching active routes...")
    all_routes = get_routes()
    routes_to_cache = [r for r in all_routes if str(r["route_id"]) in route_ids]
    _dbg(f"Caching {len(routes_to_cache)} route(s)...")

    for route_data in routes_to_cache:
        api_route_id = str(route_data["route_id"])
        label = route_data.get("route_label", api_route_id)
        _dbg(f"  {label}")
        route_db_id = db.upsert_route(conn, api_route_id, label)

        for direction in get_directions(api_route_id):
            dir_api_id = direction["direction_id"]
            dir_name = direction["direction_name"]
            dir_db_id = db.upsert_direction(conn, route_db_id, dir_api_id, dir_name)

            for stop_info in get_stops(api_route_id, dir_api_id):
                place_code = stop_info["place_code"]
                _dbg(f"    {dir_name} / {stop_info.get('description', place_code)}")
                try:
                    data = get_departures(api_route_id, dir_api_id, place_code)
                except Exception as e:
                    _dbg(f"    Skipping {place_code}: {e}")
                    continue
                stop = data["stops"][0] if data.get("stops") else None
                if not stop or stop.get("latitude") is None:
                    continue
                db.upsert_stop(conn, dir_db_id, place_code, stop["description"],
                               stop["latitude"], stop["longitude"])
        conn.commit()

    _dbg("Cache populated.")


def main():
    conn = db.connect()
    db.init(conn)

    if not db.is_populated(conn):
        _dbg("Cache empty — populating (one-time, takes a moment)...")
        populate_cache(conn)

    # TODO: config.py ROUTES should distinguish weekday / Saturday / Sunday+holiday
    # availability, since some routes run on reduced schedules or not at all.
    found_any = False

    for route_id, route_name in ROUTES:
        directions = db.get_directions(conn, route_id)
        if not directions:
            _dbg(f"No cached data for {route_name}, skipping")
            continue

        for direction in directions:
            dir_id = direction["ApiDirectionId"]
            dir_name = direction["Name"]

            cached_stops = db.get_stops(conn, route_id, dir_id)
            _dbg(f"{route_name} {dir_name}: checking {len(cached_stops)} cached stop(s)...")

            nearest_place = None
            nearest_dist = float("inf")
            for stop in cached_stops:
                dist = haversine_miles(MY_LAT, MY_LON, stop["Latitude"], stop["Longitude"])
                if dist <= RADIUS_MILES and dist < nearest_dist:
                    nearest_place = stop["PlaceCode"]
                    nearest_dist = dist

            if nearest_place is None:
                _dbg(f"  No stops within radius")
                continue
            _dbg(f"  Nearest: {nearest_place} ({nearest_dist:.3f} mi), fetching live departures...")

            try:
                data = get_departures(route_id, dir_id, nearest_place)
            except Exception as e:
                print(f"[{route_name} {dir_name}] Could not fetch departures: {e}", file=sys.stderr)
                continue

            stop_desc = data["stops"][0].get("description", nearest_place) if data.get("stops") else nearest_place
            departures = data.get("departures", [])[:MAX_ARRIVALS]
            _dbg(f"  {len(departures)} departure(s) at {stop_desc}")

            for dep in departures:
                dep_time = dep.get("departure_time")
                time_str = format_time(dep_time) if dep_time else dep.get("departure_text", "unknown")
                dir_text = dep.get("direction_text", dir_name)
                dest = dep.get("description", "")
                print(f"Route {route_name} {dir_text} toward {dest} at {stop_desc}: {time_str}")
                found_any = True

    conn.close()
    if not found_any:
        print("No upcoming arrivals found within the search radius.")


if __name__ == "__main__":
    main()
