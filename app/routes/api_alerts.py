"""Alerts API endpoints."""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from db.connection import get_db
from app.utils import serialize_doc

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.route("", methods=["GET"])
def list_alerts():
    """Lists recent anomaly alert incidents."""
    db = get_db()
    query = {}
    if "acknowledged" in request.args:
        query["acknowledged"] = request.args["acknowledged"].lower() == "true"
    if "severity" in request.args:
        query["severity"] = request.args["severity"].upper()

    alerts = list(db.alerts.find(query).sort("ts", -1).limit(50))
    return jsonify({"count": len(alerts), "alerts": serialize_doc(alerts)})


@bp.route("/<alert_id>/ack", methods=["POST"])
def acknowledge_alert(alert_id):
    """Marks an alert as acknowledged by an operator."""
    db = get_db()
    res = db.alerts.update_one(
        {"alertId": alert_id},
        {"$set": {"acknowledged": True, "acknowledgedAt": datetime.now(timezone.utc)}}
    )
    if res.matched_count == 0:
        return jsonify({"error": f"Alert '{alert_id}' not found"}), 404
    return jsonify({"message": f"Alert '{alert_id}' acknowledged."})
