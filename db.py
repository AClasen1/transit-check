import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cache.db"

_DDL = """
CREATE TABLE IF NOT EXISTS Routes (
    RouteId     INTEGER PRIMARY KEY AUTOINCREMENT,
    ApiRouteId  TEXT    NOT NULL UNIQUE,
    Label       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS RouteDirections (
    RouteDirectionId  INTEGER PRIMARY KEY AUTOINCREMENT,
    RouteId           INTEGER NOT NULL REFERENCES Routes(RouteId),
    ApiDirectionId    INTEGER NOT NULL,
    Name              TEXT    NOT NULL,
    UNIQUE (RouteId, ApiDirectionId)
);

CREATE TABLE IF NOT EXISTS RouteDirectionStops (
    RouteDirectionStopId  INTEGER PRIMARY KEY AUTOINCREMENT,
    RouteDirectionId      INTEGER NOT NULL REFERENCES RouteDirections(RouteDirectionId),
    PlaceCode             TEXT    NOT NULL,
    Description           TEXT    NOT NULL,
    Latitude              REAL    NOT NULL,
    Longitude             REAL    NOT NULL,
    UNIQUE (RouteDirectionId, PlaceCode)
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)


def is_populated(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM Routes").fetchone()[0] > 0


def upsert_route(conn: sqlite3.Connection, api_route_id: str, label: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO Routes (ApiRouteId, Label) VALUES (?, ?)",
        (api_route_id, label),
    )
    return conn.execute(
        "SELECT RouteId FROM Routes WHERE ApiRouteId = ?", (api_route_id,)
    ).fetchone()[0]


def upsert_direction(conn: sqlite3.Connection, route_id: int, api_direction_id: int, name: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO RouteDirections (RouteId, ApiDirectionId, Name) VALUES (?, ?, ?)",
        (route_id, api_direction_id, name),
    )
    return conn.execute(
        "SELECT RouteDirectionId FROM RouteDirections WHERE RouteId = ? AND ApiDirectionId = ?",
        (route_id, api_direction_id),
    ).fetchone()[0]


def upsert_stop(conn: sqlite3.Connection, route_direction_id: int, place_code: str,
                description: str, latitude: float, longitude: float) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO RouteDirectionStops
           (RouteDirectionId, PlaceCode, Description, Latitude, Longitude)
           VALUES (?, ?, ?, ?, ?)""",
        (route_direction_id, place_code, description, latitude, longitude),
    )


def get_cached_routes(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT ApiRouteId, Label FROM Routes").fetchall()


def get_directions(conn: sqlite3.Connection, api_route_id: str) -> list:
    return conn.execute(
        """SELECT d.ApiDirectionId, d.Name
           FROM RouteDirections d
           JOIN Routes r ON d.RouteId = r.RouteId
           WHERE r.ApiRouteId = ?""",
        (api_route_id,),
    ).fetchall()


def get_stops(conn: sqlite3.Connection, api_route_id: str, api_direction_id: int) -> list:
    return conn.execute(
        """SELECT s.PlaceCode, s.Description, s.Latitude, s.Longitude
           FROM RouteDirectionStops s
           JOIN RouteDirections d ON s.RouteDirectionId = d.RouteDirectionId
           JOIN Routes r ON d.RouteId = r.RouteId
           WHERE r.ApiRouteId = ? AND d.ApiDirectionId = ?""",
        (api_route_id, api_direction_id),
    ).fetchall()
