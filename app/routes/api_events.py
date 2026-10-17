"""Events Ingestion & Telemetry History API."""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta
from db.connection import get_db
from app.utils import serialize_doc

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.route("", methods=["POST"])
def ingest_events():
    """Ingests high-throughput telemetry events (supports single doc or batch list)."""
    db = get_db()
    data = request.get_json()

    if not data:
        return jsonify({"error": "Empty payload"}), 400

    now = datetime.now(timezone.utc)
    docs = data if isinstance(data, list) else [data]
    prepared = []

    for d in docs:
        if not isinstance(d, dict) or "deviceId" not in d or "readings" not in d:
            return jsonify({"error": "Each event must include 'deviceId' and 'readings'"}), 400
        if not isinstance(d["readings"], dict) or not d["readings"]:
            return jsonify({"error": "'readings' must be a non-empty object of sensor values"}), 400
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in d["readings"].values()):
            return jsonify({"error": "Every reading value must be a number"}), 400

        ts = d.get("ts")
        if isinstance(ts, str):
            try:
                parsed_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                parsed_ts = now
        else:
            parsed_ts = now

        prepared.append({
            "deviceId": d["deviceId"],
            "ts": parsed_ts,
            "readings": d["readings"],
            "status": d.get("status", "OK"),
            "errors": d.get("errors", []),
        })

    if prepared:
        db.events.insert_many(prepared)
        # Update lastSeen on the device
        device_ids = list({p["deviceId"] for p in prepared})
        db.devices.update_many(
            {"deviceId": {"$in": device_ids}},
            {"$set": {"lastSeen": now}}
        )

    return jsonify({"message": f"Successfully ingested {len(prepared)} event(s)"}), 201


@bp.route("/latest", methods=["GET"])
def get_latest_events():
    """Retrieves the most recent telemetry readings per device."""
    db = get_db()
    limit = int(request.args.get("limit", 60))

    pipeline = [
        {"$sort": {"deviceId": 1, "ts": -1}},
        {
            "$group": {
                "_id": "$deviceId",
                "latestTs": {"$first": "$ts"},
                "readings": {"$first": "$readings"},
                "status": {"$first": "$status"},
                "errors": {"$first": "$errors"},
            }
        },
        {
            "$lookup": {
                "from": "devices",
                "localField": "_id",
                "foreignField": "deviceId",
                "as": "device",
            }
        },
        {"$unwind": {"path": "$device", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "deviceId": "$_id",
                "_id": 0,
                "name": "$device.name",
                "type": "$device.type",
                "zoneId": "$device.zoneId",
                "latestTs": 1,
                "readings": 1,
                "status": 1,
                "errors": 1,
            }
        },
        {"$limit": limit},
    ]

    events = list(db.events.aggregate(pipeline))
    return jsonify({"count": len(events), "events": serialize_doc(events)})


@bp.route("/<device_id>/history", methods=["GET"])
def get_device_history(device_id):
    """Retrieves chronological telemetry time-series points for charting."""
    db = get_db()
    hours = int(request.args.get("hours", 6))
    limit = int(request.args.get("limit", 200))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    cursor = db.events.find(
        {"deviceId": device_id, "ts": {"$gte": cutoff}},
        {"_id": 0, "deviceId": 1, "ts": 1, "readings": 1, "status": 1, "errors": 1}
    ).sort("ts", 1).limit(limit)

    points = list(cursor)
    return jsonify({"deviceId": device_id, "count": len(points), "history": serialize_doc(points)})
