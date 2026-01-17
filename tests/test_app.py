import importlib
import os
import sqlite3
import sys

from fastapi.testclient import TestClient


def create_client(tmp_path):
    db_path = tmp_path / "honeykey.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    os.environ["HONEYPOT_KEY"] = "acme_live_f93k2jf92jf0s9df"
    os.environ["INCIDENT_WINDOW_MINUTES"] = "30"
    os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://localhost:3000"

    if "app.main" in sys.modules:
        del sys.modules["app.main"]
    module = importlib.import_module("app.main")
    return TestClient(module.app), db_path


def test_health_endpoint(tmp_path):
    client, _ = create_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_honeypot_detection_logs_incident(tmp_path):
    client, db_path = create_client(tmp_path)
    response = client.get(
        "/v1/projects",
        headers={"Authorization": "Bearer acme_live_f93k2jf92jf0s9df"},
    )
    assert response.status_code == 401

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    event = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert event is not None
    assert event["auth_present"] == 1
    assert event["honeypot_key_used"] == 1
    assert event["incident_id"] is not None

    incident = conn.execute(
        "SELECT * FROM incidents WHERE id = ?",
        (event["incident_id"],),
    ).fetchone()
    assert incident is not None
    assert incident["key_id"] == "honeypot"
    assert incident["event_count"] == 1
