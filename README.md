# transit-check

On-demand display of upcoming departures for a selected set of Metro Transit routes near a given location.

When run, it finds the closest stop for each configured route and direction within a search radius, then prints the next two departures for each. The result is a quick snapshot of what's coming — both directions of each route — without opening an app or website.

## What it does

For each configured route, in each direction:

1. Fetches all stops from the Metro Transit NexTrip v2 API
2. Finds the nearest stop within the search radius using the haversine (great-circle) distance formula
3. Fetches live departures for that stop and prints the next two for that route

## Configuration

Edit [config.py](config.py) to change:

| Setting | Description |
|---|---|
| `MY_LAT`, `MY_LON` | Your location (default: 46th & Snelling, Minneapolis) |
| `RADIUS_MILES` | Search radius for nearby stops (default: 0.5 mi) |
| `MAX_ARRIVALS` | Departures shown per route/direction (default: 2) |
| `ROUTES` | List of `(nextrip_route_id, display_name)` pairs to monitor |

Default routes: Blue Line (901), A Line (921), 74, 645.

## Usage

```
pip install -r requirements.txt
python main.py
```

## Tools and connections

- **Metro Transit NexTrip v2 API** (`svc.metrotransit.org/nextrip`) — provides directions, stops, and real-time departure data
- **requests** — HTTP client for the NexTrip API calls
- **Haversine formula** ([distance.py](distance.py)) — calculates straight-line distance between coordinates to find the nearest stop

## Sample API responses for reference

- sample_routes.json — A listing of active routes for the day. response to /nextrip/routes
- sample_route_direction.json — A listing of directions for a given route. response to /nextrip/directions/{route_id}
- sample_stops_route_direction.json — A listing of important stops for a given route and direction. response to /nextrip/{route_id}/{direction_id}
- sample_departures_route_direction_place.json — A listing of upcoming departures for a given route, direction, and place_code. response to /nextrip/{route_id}/{direction_id}/{place_code}
