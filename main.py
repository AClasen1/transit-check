import sys
import db

from config import MAX_ARRIVALS, MY_LAT, MY_LON, RADIUS_MILES, ROUTES
from distance import haversine_miles
from nextrip import get_departures, get_directions, get_routes, get_stops




def populate_cache(conn: db.sqlite3.Connection) -> None:
    route_ids = {rid for rid, _ in ROUTES}
    all_routes = get_routes()

    for route_data in [r for r in all_routes if str(r["route_id"]) in route_ids]:
        api_route_id = str(route_data["route_id"])
        route_db_id = db.upsert_route(conn, api_route_id, route_data.get("route_label", api_route_id))

        for direction in get_directions(api_route_id):
            dir_api_id = direction["direction_id"]
            dir_db_id = db.upsert_direction(conn, route_db_id, dir_api_id, direction["direction_name"])

            for stop_info in get_stops(api_route_id, dir_api_id):
                place_code = stop_info["place_code"]
                try:
                    data = get_departures(api_route_id, dir_api_id, place_code)
                except Exception:
                    continue
                stop = data["stops"][0] if data.get("stops") else None
                if not stop or stop.get("latitude") is None:
                    continue
                db.upsert_stop(conn, dir_db_id, place_code, stop["description"],
                               stop["latitude"], stop["longitude"])
        conn.commit()


def validate_cache(conn: db.sqlite3.Connection) -> None:
    configured_ids = {rid for rid, _ in ROUTES}
    configured_labels = {rid: label for rid, label in ROUTES}

    try:
        api_routes = get_routes()
    except Exception as e:
        print(f"Could not fetch routes from API: {e}", file=sys.stderr)
        return

    api_route_map = {str(r["route_id"]): r.get("route_label", str(r["route_id"])) for r in api_routes}
    cached_route_ids = {r["ApiRouteId"] for r in db.get_cached_routes(conn)}

    print("=== Routes ===")
    for rid in sorted(configured_ids):
        label = configured_labels[rid]
        if rid not in api_route_map:
            print(f"  [{rid}] {label}: NOT FOUND in API")
        elif rid not in cached_route_ids:
            print(f"  [{rid}] {label}: in API but MISSING from cache")
        else:
            print(f"  [{rid}] {label}: OK")

    for rid in sorted(configured_ids):
        if rid not in api_route_map:
            continue
        label = configured_labels.get(rid, rid)
        print(f"\n=== {label} (route {rid}) ===")

        try:
            api_dirs = get_directions(rid)
        except Exception as e:
            print(f"  Could not fetch directions: {e}")
            continue

        api_dir_ids = {d["direction_id"] for d in api_dirs}
        cached_dirs = db.get_directions(conn, rid)
        cached_dir_ids = {d["ApiDirectionId"] for d in cached_dirs}
        missing_dirs = api_dir_ids - cached_dir_ids

        if missing_dirs:
            print(f"  Directions MISSING from cache: {sorted(missing_dirs)}")
        else:
            print(f"  Directions: {len(api_dirs)} OK")

        for d in api_dirs:
            dir_id = d["direction_id"]
            dir_name = d["direction_name"]
            try:
                api_stops = get_stops(rid, dir_id)
            except Exception as e:
                print(f"  [{dir_name}] Could not fetch stops: {e}")
                continue

            api_place_codes = {s["place_code"] for s in api_stops}
            cached_stops = db.get_stops(conn, rid, dir_id)
            cached_place_codes = {s["PlaceCode"] for s in cached_stops}
            missing_codes = api_place_codes - cached_place_codes

            if not cached_place_codes:
                status = "ERROR: no stops cached"
            elif missing_codes:
                status = f"{len(cached_place_codes)}/{len(api_place_codes)} stops cached"
            else:
                status = f"all {len(api_place_codes)} stops cached"

            print(f"  [{dir_name}] {status}")
            if missing_codes:
                print(f"    not cached (no coords from departures API): {sorted(missing_codes)}")


def main():
    conn = db.connect()
    db.init(conn)

    if "--flush" in sys.argv:
        db.flush(conn)
        print("Cache flushed.")
        conn.close()
        return

    if "--validate" in sys.argv:
        if not db.is_populated(conn):
            print("Cache is empty — run without --validate first to populate it.", file=sys.stderr)
        else:
            validate_cache(conn)
        conn.close()
        return

    if not db.is_populated(conn):
        print("Building stop cache (one-time)...", file=sys.stderr)
        populate_cache(conn)

    # TODO: config.py ROUTES should distinguish weekday / Saturday / Sunday+holiday
    # availability, since some routes run on reduced schedules or not at all.
    found_any = False

    for route_id, route_name in ROUTES:
        directions = db.get_directions(conn, route_id)

        for direction in directions:
            dir_id = direction["ApiDirectionId"]
            dir_name = direction["Name"]

            nearest_place = None
            nearest_dist = float("inf")
            for stop in db.get_stops(conn, route_id, dir_id):
                dist = haversine_miles(MY_LAT, MY_LON, stop["Latitude"], stop["Longitude"])
                if dist <= RADIUS_MILES and dist < nearest_dist:
                    nearest_place = stop["PlaceCode"]
                    nearest_dist = dist

            if nearest_place is None:
                continue

            try:
                data = get_departures(route_id, dir_id, nearest_place)
            except Exception as e:
                print(f"[{route_name} {dir_name}] Could not fetch departures: {e}", file=sys.stderr)
                continue

            label = f"Route {route_name}" if route_name.isdigit() else route_name
            departures = data.get("departures", [])[:MAX_ARRIVALS]

            if not departures:
                print(f"{label} {dir_name}: No scheduled departures")
                found_any = True
                continue

            stop_desc = data["stops"][0].get("description", nearest_place) if data.get("stops") else nearest_place
            for dep in departures:
                print(f"{label} {dir_name[0]} at {stop_desc}: {dep.get('departure_text', 'unknown')}")
                found_any = True

    conn.close()
    if not found_any:
        print("No upcoming arrivals found within the search radius.")


if __name__ == "__main__":
    main()
