from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Generator, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

DEFAULT_DB_PATH = "./data/honeykey.db"
DEFAULT_INCIDENT_WINDOW_MINUTES = 30

DATABASE_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
HONEYPOT_KEY = os.getenv("HONEYPOT_KEY", "")
INCIDENT_WINDOW_MINUTES = int(
    os.getenv("INCIDENT_WINDOW_MINUTES", str(DEFAULT_INCIDENT_WINDOW_MINUTES))
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app = FastAPI(title="HoneyKey Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                ip TEXT,
                method TEXT,
                path TEXT,
                user_agent TEXT,
                correlation_id TEXT,
                auth_present INTEGER,
                honeypot_key_used INTEGER,
                incident_id INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                event_count INTEGER NOT NULL
            )
            """
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class Incident(BaseModel):
    id: int
    key_id: str
    source_ip: str
    first_seen: str
    last_seen: str
    event_count: int


class Event(BaseModel):
    id: int
    ts: str
    ip: Optional[str]
    method: Optional[str]
    path: Optional[str]
    user_agent: Optional[str]
    correlation_id: Optional[str]
    auth_present: bool
    honeypot_key_used: bool
    incident_id: Optional[int]


class HealthResponse(BaseModel):
    status: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def find_or_create_incident(conn: sqlite3.Connection, source_ip: str, key_id: str) -> int:
    window_start = utc_now() - timedelta(minutes=INCIDENT_WINDOW_MINUTES)
    window_start_iso = window_start.isoformat()
    existing = conn.execute(
        """
        SELECT id, event_count
        FROM incidents
        WHERE source_ip = ?
          AND key_id = ?
          AND last_seen >= ?
        ORDER BY last_seen DESC
        LIMIT 1
        """,
        (source_ip, key_id, window_start_iso),
    ).fetchone()
    now_iso = utc_now().isoformat()
    if existing:
        conn.execute(
            """
            UPDATE incidents
            SET last_seen = ?, event_count = ?
            WHERE id = ?
            """,
            (now_iso, existing["event_count"] + 1, existing["id"]),
        )
        return int(existing["id"])

    cursor = conn.execute(
        """
        INSERT INTO incidents (key_id, source_ip, first_seen, last_seen, event_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (key_id, source_ip, now_iso, now_iso, 1),
    )
    return int(cursor.lastrowid)


@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Any:
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    auth_header = request.headers.get("authorization")
    auth_present = bool(auth_header)
    token = parse_bearer_token(auth_header)
    honeypot_key_used = bool(token and HONEYPOT_KEY and token == HONEYPOT_KEY)

    response = await call_next(request)
    response.headers["x-correlation-id"] = correlation_id

    now_iso = utc_now().isoformat()
    client_ip = request.client.host if request.client else None
    key_id = "honeypot" if honeypot_key_used else None
    with get_db() as conn:
        incident_id = None
        if honeypot_key_used and client_ip:
            incident_id = find_or_create_incident(conn, client_ip, key_id)

        conn.execute(
            """
            INSERT INTO events (
                ts, ip, method, path, user_agent,
                correlation_id, auth_present, honeypot_key_used, incident_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso,
                client_ip,
                request.method,
                request.url.path,
                request.headers.get("user-agent"),
                correlation_id,
                int(auth_present),
                int(honeypot_key_used),
                incident_id,
            ),
        )

    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/v1/projects")
async def trap_projects() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/v1/secrets")
async def trap_secrets() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/v1/auth/verify")
async def trap_verify() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/incidents", response_model=List[Incident])
async def list_incidents() -> List[Incident]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, key_id, source_ip, first_seen, last_seen, event_count
            FROM incidents
            ORDER BY last_seen DESC
            """
        ).fetchall()
    return [Incident(**dict(row)) for row in rows]


@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: int) -> Incident:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, key_id, source_ip, first_seen, last_seen, event_count
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return Incident(**dict(row))


@app.get("/incidents/{incident_id}/events", response_model=List[Event])
async def get_incident_events(incident_id: int) -> List[Event]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, ts, ip, method, path, user_agent, correlation_id,
                   auth_present, honeypot_key_used, incident_id
            FROM events
            WHERE incident_id = ?
            ORDER BY ts DESC
            """,
            (incident_id,),
        ).fetchall()
    return [
        Event(
            **{
                **dict(row),
                "auth_present": bool(row["auth_present"]),
                "honeypot_key_used": bool(row["honeypot_key_used"]),
            }
        )
        for row in rows
    ]
