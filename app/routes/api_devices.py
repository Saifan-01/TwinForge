"""Device CRUD & Geospatial Fleet API endpoints."""

import re

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from pymongo.errors import WriteError, DuplicateKeyError
from db.connection import get_db
from app.utils import serialize_doc

bp = Blueprint("devices", __name__, url_prefix="/api/devices")

DEVICE_ID_RE = re.compile(r"^DEV-[A-Z0-9-]+$")
DEVICE_TYPES = {"CNC_MILL", "AGV_FORKLIFT", "POWER_TRANSFORMER", "HVAC_CHILLER",
                "CLEANROOM_MONITOR", "VIBRATION_SENSOR"}
DEVICE_STATUSES = {"ONLINE", "WARNING", "CRITICAL", "MAINTENANCE", "DECOMMISSIONED"}
UPDATABLE_FIELDS = {"name", "zoneId", "status", "capabilities", "specs", "location", "firmwareVersion"}


def validate_device_fields(payload, partial=False):
    """Returns an error string for the first invalid field, or None when valid."""
    if "deviceId" in payload and not (isinstance(payload["deviceId"], str) and DEVICE_ID_RE.match(payload["deviceId"])):
        return "deviceId must look like DEV-ABC-001 (capital letters, digits and dashes)"
    for key in ("name", "zoneId", "firmwareVersion"):
        if key in payload and not (isinstance(payload[key], str) and 0 < len(payload[key].strip()) <= 120):
            return f"{key} must be a non-empty text value (max 120 characters)"
    if "type" in payload and payload["type"] not in DEVICE_TYPES:
        return f"type must be one of: {', '.join(sorted(DEVICE_TYPES))}"
    if "status" in payload and payload["status"] not in DEVICE_STATUSES:
        return f"status must be one of: {', '.join(sorted(DEVICE_STATUSES))}"
    if "capabilities" in payload:
        caps = payload["capabilities"]
        if not (isinstance(caps, list) and caps and all(isinstance(c, str) and c for c in caps)):
            return "capabilities must be a non-empty list of sensor names"
    if "specs" in payload and not isinstance(payload["specs"], dict):
        return "specs must be an object"
    if "location" in payload:
        loc = payload["location"]
        coords = loc.get("coordinates") if isinstance(loc, dict) else None
        if not (isinstance(loc, dict) and loc.get("type") == "Point" and isinstance(coords, list)
                and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords)):
            return "location must be a GeoJSON Point: {type: 'Point', coordinates: [lng, lat]}"
    return None


@bp.route("", methods=["GET"])
def list_devices():
    """Retrieves registered devices with optional zoneId, type, and status filters."""
    db = get_db()
    query = {}
    if "zoneId" in request.args:
        query["zoneId"] = request.args["zoneId"]
    if "type" in request.args:
        query["type"] = request.args["type"]
    if "status" in request.args:
        query["status"] = request.args["status"]

    devices = list(db.devices.find(query).sort("deviceId", 1))
    return jsonify({"count": len(devices), "devices": serialize_doc(devices)})


@bp.route("/<device_id>", methods=["GET"])
def get_device(device_id):
    """Retrieves a single device by its unique deviceId."""
    db = get_db()
    device = db.devices.find_one({"deviceId": device_id})
    if not device:
        return jsonify({"error": f"Device '{device_id}' not found"}), 404
    return jsonify(serialize_doc(device))


@bp.route("", methods=["POST"])
def register_device():
    """Registers a new industrial IoT device into the digital twin."""
    db = get_db()
    payload = request.get_json() or {}

    required = ["deviceId", "name", "type", "zoneId", "status", "capabilities"]
    for r in required:
        if r not in payload:
            return jsonify({"error": f"Missing required field: '{r}'"}), 400
    problem = validate_device_fields(payload)
    if problem:
        return jsonify({"error": problem}), 400

    now = datetime.now(timezone.utc)
    device_doc = {
        "deviceId": payload["deviceId"],
        "name": payload["name"],
        "type": payload["type"],
        "zoneId": payload["zoneId"],
        "status": payload.get("status", "ONLINE"),
        "capabilities": payload["capabilities"],
        "specs": payload.get("specs", {}),
        "location": payload.get("location", {
            "type": "Point",
            "coordinates": [-84.3880, 33.7490],
        }),
        "installedAt": now,
        "lastSeen": now,
        "firmwareVersion": payload.get("firmwareVersion", "v1.0.0"),
    }

    try:
        res = db.devices.insert_one(device_doc)
        return jsonify({
            "message": "Device registered successfully",
            "deviceId": payload["deviceId"],
            "_id": str(res.inserted_id),
        }), 201
    except DuplicateKeyError:
        return jsonify({"error": f"Device with ID '{payload['deviceId']}' already exists."}), 409
    except WriteError as e:
        return jsonify({"error": "Schema validation failed", "details": str(e)}), 422


@bp.route("/<device_id>", methods=["PUT"])
def update_device(device_id):
    """Updates device specifications, operational status, or zone assignment."""
    db = get_db()
    payload = request.get_json() or {}

    # Only whitelisted fields may change (deviceId is immutable)
    payload.pop("deviceId", None)
    payload.pop("_id", None)
    unknown = set(payload) - UPDATABLE_FIELDS
    if unknown:
        return jsonify({"error": f"Fields not editable: {', '.join(sorted(unknown))}"}), 400
    if not payload:
        return jsonify({"error": "No editable fields supplied"}), 400
    problem = validate_device_fields(payload, partial=True)
    if problem:
        return jsonify({"error": problem}), 400
    payload["lastSeen"] = datetime.now(timezone.utc)

    res = db.devices.update_one({"deviceId": device_id}, {"$set": payload})
    if res.matched_count == 0:
        return jsonify({"error": f"Device '{device_id}' not found"}), 404

    return jsonify({"message": "Device updated successfully", "modifiedCount": res.modified_count})


@bp.route("/<device_id>", methods=["DELETE"])
def decommission_device(device_id):
    """Sets device lifecycle status to DECOMMISSIONED (soft purge) or deletes."""
    db = get_db()
    purge = request.args.get("hard", "false").lower() == "true"

    if purge:
        res = db.devices.delete_one({"deviceId": device_id})
        if res.deleted_count == 0:
            return jsonify({"error": f"Device '{device_id}' not found"}), 404
        return jsonify({"message": f"Device '{device_id}' purged from digital twin."})
    else:
        res = db.devices.update_one(
            {"deviceId": device_id},
            {"$set": {"status": "DECOMMISSIONED", "decommissionedAt": datetime.now(timezone.utc)}}
        )
        if res.matched_count == 0:
            return jsonify({"error": f"Device '{device_id}' not found"}), 404
        return jsonify({"message": f"Device '{device_id}' marked as DECOMMISSIONED."})


@bp.route("/near", methods=["GET"])
def find_nearby_devices():
    """Geospatial proximity query using MongoDB 2dsphere index and $near operator."""
    db = get_db()
    try:
        lng = float(request.args.get("lng", -84.3880))
        lat = float(request.args.get("lat", 33.7490))
        max_dist = float(request.args.get("max_distance_meters", 1000))
    except ValueError:
        return jsonify({"error": "Invalid lng/lat/distance numbers provided"}), 400

    geo_query = {
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": max_dist,
            }
        }
    }

    devices = list(db.devices.find(geo_query).limit(20))
    return jsonify({
        "center": [lng, lat],
        "maxDistanceMeters": max_dist,
        "count": len(devices),
        "devices": serialize_doc(devices),
    })
