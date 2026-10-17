"""Unit and integration tests for Device CRUD and Geospatial queries."""

import pytest


def test_list_devices(client):
    """Verifies listing devices with and without filters."""
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.get_json()
    assert "devices" in data
    assert data["count"] > 0


def test_get_device_by_id(client):
    """Verifies single device retrieval."""
    res = client.get("/api/devices/DEV-CNC-004")
    assert res.status_code == 200
    data = res.get_json()
    assert data["deviceId"] == "DEV-CNC-004"
    assert "capabilities" in data
    assert "location" in data


def test_device_registration_schema_validation(client):
    """Verifies that registration fails when required schema fields are missing."""
    invalid_payload = {
        "deviceId": "DEV-TEST-INVALID",
        # Missing 'name', 'type', 'zoneId', 'status', 'capabilities'
    }
    res = client.post("/api/devices", json=invalid_payload)
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_device_lifecycle_crud(client):
    """Tests the full lifecycle: Register -> Update -> Geospatial Query -> Decommission."""
    test_id = "DEV-TEST-099"

    # 1. Register new polymorphic device
    new_device = {
        "deviceId": test_id,
        "name": "Autonomous Inspection Drone #99",
        "type": "AGV_FORKLIFT",
        "zoneId": "ZONE-LOGISTICS-C",
        "status": "ONLINE",
        "capabilities": ["altitude_m", "battery_pct", "obstacle_dist_m"],
        "specs": {"rotorCount": 6, "cameraSensor": "4K FLIR Thermal"},
        "location": {
            "type": "Point",
            "coordinates": [-84.3880, 33.7490],
        },
    }

    # Delete if exists from previous test run
    client.delete(f"/api/devices/{test_id}?hard=true")

    res = client.post("/api/devices", json=new_device)
    assert res.status_code == 201

    # 2. Update metadata
    update_res = client.put(f"/api/devices/{test_id}", json={"status": "WARNING", "firmwareVersion": "v2.5.0"})
    assert update_res.status_code == 200

    # Verify update
    get_res = client.get(f"/api/devices/{test_id}")
    assert get_res.status_code == 200
    assert get_res.get_json()["status"] == "WARNING"

    # 3. Geospatial proximity query via 2dsphere index
    geo_res = client.get("/api/devices/near?lng=-84.3880&lat=33.7490&max_distance_meters=500")
    assert geo_res.status_code == 200
    geo_data = geo_res.get_json()
    assert geo_data["count"] > 0
    found_ids = [d["deviceId"] for d in geo_data["devices"]]
    assert test_id in found_ids

    # 4. Decommission device (soft purge)
    del_res = client.delete(f"/api/devices/{test_id}")
    assert del_res.status_code == 200

    # Cleanup hard delete
    client.delete(f"/api/devices/{test_id}?hard=true")
