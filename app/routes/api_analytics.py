"""Analytics & Aggregation Queries API endpoints."""

from flask import Blueprint, request, jsonify
from db.connection import get_db
from queries.unusual_events import run_unusual_events_query
from queries.failure_prediction import run_failure_prediction_query
from app.utils import serialize_doc
import os

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@bp.route("/unusual-today", methods=["GET"])
def get_unusual_events():
    """Query 1: 'Show me everything unusual that happened in the factory today'.
    Executes $setWindowFields statistical rolling Z-score & error aggregation.
    """
    hours = int(request.args.get("hours", 24))
    z_threshold = float(request.args.get("z_threshold", 2.5))
    results = run_unusual_events_query(hours=hours, z_threshold=z_threshold)
    return jsonify({
        "query": "unusual_today",
        "timeWindowHours": hours,
        "zScoreThreshold": z_threshold,
        "count": len(results),
        "unusualEvents": serialize_doc(results),
    })


@bp.route("/failure-risk", methods=["GET"])
def get_failure_risk():
    """Query 2: 'Which machines show signs of failure?'.
    Executes multi-metric trend pipeline (vibration escalation, thermal rise, error frequencies).
    """
    hours = int(request.args.get("hours", 12))
    results = run_failure_prediction_query(hours=hours)
    return jsonify({
        "query": "failure_prediction",
        "trendWindowHours": hours,
        "count": len(results),
        "machines": serialize_doc(results),
    })


@bp.route("/overview", methods=["GET"])
def get_plant_overview():
    """High-level plant digital twin operational summary for dashboard counters."""
    db = get_db()
    total_devices = db.devices.count_documents({})
    online_devices = db.devices.count_documents({"status": "ONLINE"})
    warning_devices = db.devices.count_documents({"status": "WARNING"})
    critical_devices = db.devices.count_documents({"status": "CRITICAL"})
    total_events = db.events.count_documents({})
    unack_alerts = db.alerts.count_documents({"acknowledged": False})

    # Zone summary
    zones = list(db.zones.find({}, {"_id": 0}))
    for z in zones:
        z["deviceCount"] = db.devices.count_documents({"zoneId": z["zoneId"]})

    return jsonify({
        "totalDevices": total_devices,
        "onlineDevices": online_devices,
        "warningDevices": warning_devices,
        "criticalDevices": critical_devices,
        "totalEvents": total_events,
        "activeAlerts": unack_alerts,
        "zones": zones,
    })


@bp.route("/benchmark", methods=["GET"])
def get_benchmark_report():
    """Returns stored benchmark evidence markdown or cached metrics."""
    doc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results.md"))
    content = ""
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
    return jsonify({"reportMarkdown": content})
