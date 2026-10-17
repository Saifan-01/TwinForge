"""Tests for polymorphic telemetry events ingestion and retrieval."""

import pytest
from datetime import datetime, timezone


def test_polymorphic_event_ingestion(client):
    """Verifies that events with completely distinct schemas are accepted seamlessly."""

    # Event 1: CNC Machining Center (vibration, temp, pressure, rpm)
    cnc_event = {
        "deviceId": "DEV-CNC-001",
        "readings": {
            "vibration_mms": 1.95,
            "temperature_c": 51.2,
            "pressure_bar": 6.8,
            "spindle_rpm": 9250,
        },
        "status": "OK",
        "errors": [],
    }

    # Event 2: AGV Transport Unit (gps_speed, battery, location)
    agv_event = {
        "deviceId": "DEV-AGV-001",
        "readings": {
            "gps_speed_kph": 5.4,
            "battery_pct": 82.5,
            "motor_temp_c": 39.1,
            "heading_deg": 185,
        },
        "status": "OK",
        "errors": [],
    }

    # Event 3: Electrical Distribution Unit (voltage, current, power factor)
    pdu_event = {
        "deviceId": "DEV-PDU-001",
        "readings": {
            "voltage_v": 401.8,
            "current_a": 192.5,
            "power_factor": 0.96,
            "energy_kwh": 14280.5,
        },
        "status": "OK",
        "errors": [],
    }

    # Ingest batch
    res = client.post("/api/events", json=[cnc_event, agv_event, pdu_event])
    assert res.status_code == 201
    assert "Successfully ingested 3 event(s)" in res.get_json()["message"]


def test_device_history_lookup(client):
    """Verifies retrieving chronological time-series points for a device."""
    res = client.get("/api/events/DEV-CNC-004/history?hours=24&limit=50")
    assert res.status_code == 200
    data = res.get_json()
    assert data["deviceId"] == "DEV-CNC-004"
    assert data["count"] > 0
    assert "readings" in data["history"][0]


def test_latest_events_feed(client):
    """Verifies the latest snapshot query across the factory."""
    res = client.get("/api/events/latest?limit=20")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] > 0
    assert "events" in data
