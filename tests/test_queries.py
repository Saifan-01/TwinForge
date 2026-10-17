"""Tests for the two rubric analytical queries."""

import pytest
from queries.unusual_events import run_unusual_events_query
from queries.failure_prediction import run_failure_prediction_query


def test_query_1_unusual_events_direct():
    """Directly tests Query 1 aggregation pipeline logic."""
    results = run_unusual_events_query(hours=24, z_threshold=2.5)
    assert isinstance(results, list)
    assert len(results) > 0

    # Ensure pre-injected anomalous devices DEV-CNC-004 and DEV-AGV-007 are flagged
    flagged_ids = [r["deviceId"] for r in results]
    assert "DEV-CNC-004" in flagged_ids or "DEV-AGV-007" in flagged_ids

    # Inspect structure of returned results
    sample = results[0]
    assert "anomalyType" in sample
    assert "readings" in sample
    assert "status" in sample


def test_query_1_endpoint(client):
    """Tests the REST endpoint for Query 1."""
    res = client.get("/api/analytics/unusual-today?hours=24&z_threshold=2.5")
    assert res.status_code == 200
    data = res.get_json()
    assert data["query"] == "unusual_today"
    assert "unusualEvents" in data
    assert data["count"] > 0


def test_query_2_failure_prediction_direct():
    """Directly tests Query 2 predictive failure ranking pipeline."""
    machines = run_failure_prediction_query(hours=12)
    assert isinstance(machines, list)
    assert len(machines) > 0

    # The top machine should be the one experiencing vibration and temp escalation
    top_machine = machines[0]
    assert top_machine["deviceId"] == "DEV-CNC-004"
    assert top_machine["failureRiskScore"] >= 75.0
    assert top_machine["riskCategory"] == "CRITICAL_FAILURE_IMMINENT"
    assert top_machine["maxVibe"] > 7.0
    assert top_machine["vibeDelta"] > 0.0


def test_query_2_endpoint(client):
    """Tests the REST endpoint for Query 2."""
    res = client.get("/api/analytics/failure-risk?hours=12")
    assert res.status_code == 200
    data = res.get_json()
    assert data["query"] == "failure_prediction"
    assert "machines" in data
    assert data["count"] > 0
