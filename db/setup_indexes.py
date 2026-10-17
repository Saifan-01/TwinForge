"""Sets up MongoDB collections, schema validation, and indexes programmatically."""

import sys
import os
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel

# Ensure root directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.connection import get_db, check_connection


def setup_schema_and_indexes():
    conn_info = check_connection()
    if conn_info["status"] != "connected":
        print(f"Error: Unable to connect to MongoDB at {conn_info.get('uri')}")
        print(f"Details: {conn_info.get('error')}")
        return False

    db = get_db()
    print(f"Connected to database '{db.name}'. Configuring collections and indexes...")

    existing_collections = db.list_collection_names()

    # 1. Create or ensure collections
    if "devices" not in existing_collections:
        db.create_collection("devices")
        print("Created collection: devices")

    if "zones" not in existing_collections:
        db.create_collection("zones")
        print("Created collection: zones")

    if "alerts" not in existing_collections:
        db.create_collection("alerts")
        print("Created collection: alerts")

    if "users" not in existing_collections:
        db.create_collection("users")
        print("Created collection: users")

    # Time-series collection for events (if supported by MongoDB edition/version)
    if "events" not in existing_collections:
        try:
            # MongoDB 5.0+ native time-series collection with built-in retention
            db.create_collection(
                "events",
                timeseries={
                    "timeField": "ts",
                    "metaField": "deviceId",
                    "granularity": "seconds",
                },
                expireAfterSeconds=604800,  # 7 days TTL retention
            )
            print("Created native Time-Series collection: events (7-day TTL)")
        except Exception as e:
            # Fallback to standard collection if running an environment where TS collections are restricted
            print(f"Note: Standard collection fallback for 'events' ({e})")
            db.create_collection("events")

    # 2. Devices Indexes
    print("Applying indexes on 'devices'...")
    db.devices.create_index([("deviceId", ASCENDING)], unique=True, name="idx_device_unique_id")
    db.devices.create_index([("location", GEOSPHERE)], name="idx_device_2dsphere_loc")
    db.devices.create_index([("zoneId", ASCENDING), ("status", ASCENDING)], name="idx_device_zone_status")
    db.devices.create_index([("type", ASCENDING), ("status", ASCENDING)], name="idx_device_type_status")

    # 3. Events Indexes
    print("Applying indexes on 'events'...")
    try:
        # Note: In MongoDB Time-Series collections, (metaField + timeField) index is automatically managed.
        # Additional secondary indexes can be added on measurements or metaField:
        db.events.create_index([("deviceId", ASCENDING), ("ts", DESCENDING)], name="idx_events_device_ts")
        db.events.create_index([("status", ASCENDING)], name="idx_events_status")
    except Exception as e:
        print(f"Notice during events index creation: {e}")

    # 4. Alerts Indexes
    print("Applying indexes on 'alerts'...")
    db.alerts.create_index(
        [("deviceId", ASCENDING), ("acknowledged", ASCENDING), ("ts", DESCENDING)],
        name="idx_alerts_dev_ack_ts",
    )
    db.alerts.create_index(
        [("severity", ASCENDING), ("acknowledged", ASCENDING)],
        name="idx_alerts_severity_ack",
    )

    # 5. Zones Indexes
    print("Applying indexes on 'zones'...")
    db.zones.create_index([("zoneId", ASCENDING)], unique=True, name="idx_zone_unique_id")

    # 6. Users Indexes (login accounts)
    print("Applying indexes on 'users'...")
    db.users.create_index([("username", ASCENDING)], unique=True, name="idx_user_unique_name")

    # 7. Apply $jsonSchema validation rules (enforced: invalid documents are rejected)
    print("Configuring $jsonSchema validation rules...")
    device_schema = {
        "bsonType": "object",
        "required": ["deviceId", "name", "type", "zoneId", "status", "capabilities"],
        "properties": {
            "deviceId": {"bsonType": "string", "pattern": "^DEV-[A-Z0-9-]+$"},
            "name": {"bsonType": "string"},
            "type": {"enum": ["CNC_MILL", "AGV_FORKLIFT", "POWER_TRANSFORMER",
                              "HVAC_CHILLER", "CLEANROOM_MONITOR", "VIBRATION_SENSOR"]},
            "zoneId": {"bsonType": "string"},
            "status": {"enum": ["ONLINE", "WARNING", "CRITICAL", "MAINTENANCE", "DECOMMISSIONED"]},
            "capabilities": {"bsonType": "array", "minItems": 1, "items": {"bsonType": "string"}},
            "location": {
                "bsonType": "object",
                "required": ["type", "coordinates"],
                "properties": {
                    "type": {"enum": ["Point"]},
                    "coordinates": {"bsonType": "array", "minItems": 2, "maxItems": 2,
                                    "items": {"bsonType": ["double", "int", "long"]}},
                },
            },
            "specs": {"bsonType": "object"},
        },
    }
    alert_schema = {
        "bsonType": "object",
        "required": ["alertId", "deviceId", "severity", "message", "ts"],
        "properties": {
            "alertId": {"bsonType": "string"},
            "deviceId": {"bsonType": "string"},
            "severity": {"enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "message": {"bsonType": "string"},
            "acknowledged": {"bsonType": "bool"},
            "ts": {"bsonType": "date"},
        },
    }
    user_schema = {
        "bsonType": "object",
        "required": ["username", "passwordHash", "role"],
        "properties": {
            "username": {"bsonType": "string", "minLength": 3},
            "passwordHash": {"bsonType": "string"},
            "role": {"enum": ["admin", "viewer"]},
        },
    }
    for coll, schema in (("devices", device_schema), ("alerts", alert_schema), ("users", user_schema)):
        try:
            db.command({
                "collMod": coll,
                "validator": {"$jsonSchema": schema},
                "validationLevel": "strict",
                "validationAction": "error",
            })
            print(f"Schema validation enforced on '{coll}'.")
        except Exception as e:
            print(f"Note: could not register validator for '{coll}' ({e})")

    print("\n--- Setup Complete! Active Indexes ---")
    for coll_name in ["devices", "events", "alerts", "zones"]:
        idx_info = list(db[coll_name].list_indexes())
        print(f"{coll_name}: {[i['name'] for i in idx_info]}")

    return True


if __name__ == "__main__":
    setup_schema_and_indexes()
