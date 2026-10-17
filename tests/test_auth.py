"""Authentication, role-based access control and input-validation tests."""

from app import auth


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def test_api_requires_credentials(anon_client):
    assert anon_client.get("/api/devices").status_code == 401
    assert anon_client.post("/api/devices", json={}).status_code == 401
    assert anon_client.delete("/api/devices/DEV-CNC-001").status_code == 401


def test_wrong_api_key_is_rejected(anon_client):
    res = anon_client.get("/api/devices", headers={"X-API-Key": "not-the-key"})
    assert res.status_code == 401


def test_valid_api_key_allows_access(client):
    assert client.get("/api/devices").status_code == 200


def test_dashboard_redirects_to_login_when_logged_out(anon_client):
    res = anon_client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_bad_password_is_rejected(anon_client, test_users):
    res = login(anon_client, "pytest_admin", "wrong-password")
    assert res.status_code == 401


def test_viewer_can_read_but_not_write(anon_client, test_users):
    assert login(anon_client, "pytest_viewer", "ViewerPass#123").status_code == 302
    assert anon_client.get("/api/devices").status_code == 200
    res = anon_client.post("/api/devices", json={}, headers={"X-Requested-With": "dashboard"})
    assert res.status_code == 403


def test_admin_session_write_needs_csrf_header(anon_client, test_users):
    assert login(anon_client, "pytest_admin", "AdminPass#123").status_code == 302
    assert anon_client.post("/api/devices", json={}).status_code == 403
    res = anon_client.post("/api/devices", json={}, headers={"X-Requested-With": "dashboard"})
    assert res.status_code == 400  # passes access control, fails payload validation


def test_login_lockout_after_repeated_failures(anon_client, test_users):
    auth._failed_logins.clear()
    for _ in range(auth.MAX_FAILED_LOGINS):
        login(anon_client, "pytest_admin", "bad")
    res = login(anon_client, "pytest_admin", "AdminPass#123")
    assert res.status_code == 401  # locked out even with the right password
    auth._failed_logins.clear()


def test_invalid_device_payloads_are_rejected(client):
    base = {"deviceId": "DEV-TEST-500", "name": "Bad device", "type": "CNC_MILL",
            "zoneId": "ZONE-MACHINING-B", "status": "ONLINE", "capabilities": ["vibration_mms"]}
    for override in (
        {"deviceId": "lowercase-id"},
        {"type": "TOASTER"},
        {"status": "EXPLODING"},
        {"capabilities": []},
        {"location": {"type": "Point", "coordinates": ["a", "b"]}},
    ):
        res = client.post("/api/devices", json={**base, **override})
        assert res.status_code == 400, override


def test_device_update_rejects_unknown_fields(client):
    res = client.put("/api/devices/DEV-CNC-001", json={"isAdmin": True})
    assert res.status_code == 400


def test_event_readings_must_be_numeric(client):
    res = client.post("/api/events", json={"deviceId": "DEV-CNC-001", "readings": {"vibration_mms": "high"}})
    assert res.status_code == 400
