"""Seeds realistic factory zones, polymorphic devices, historical telemetry, and baseline alerts."""

import sys
import os
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.connection import get_db, check_connection
from db.setup_indexes import setup_schema_and_indexes


# Factory bounding anchor (coordinates around a realistic industrial plant park)
BASE_LNG = -84.3880
BASE_LAT = 33.7490

ZONES = [
    {
        "zoneId": "ZONE-ASSEMBLY-A",
        "name": "Chassis Assembly Line A",
        "floor": 1,
        "facility": "Plant Alpha",
        "type": "Robotic Assembly",
        "description": "High-throughput robotic articulation and welding station",
    },
    {
        "zoneId": "ZONE-MACHINING-B",
        "name": "Precision CNC Machining Bay B",
        "floor": 1,
        "facility": "Plant Alpha",
        "type": "Subtractive Machining",
        "description": "5-axis milling, grinding, and automated lathe cells",
    },
    {
        "zoneId": "ZONE-LOGISTICS-C",
        "name": "Automated Logistics & Warehouse C",
        "floor": 1,
        "facility": "Plant Alpha",
        "type": "Fleet Logistics",
        "description": "Autonomous Mobile Robots (AMR) material routing depot",
    },
    {
        "zoneId": "ZONE-ENERGY-D",
        "name": "High-Voltage Power & Substation D",
        "floor": "Basement",
        "facility": "Plant Alpha",
        "type": "Power Infrastructure",
        "description": "Industrial step-down transformers, switchgear, and capacitor banks",
    },
    {
        "zoneId": "ZONE-CLEANROOM-E",
        "name": "Environmental Cleanroom E",
        "floor": 2,
        "facility": "Plant Alpha",
        "type": "Controlled Atmosphere",
        "description": "Class 10,000 cleanroom chamber for sensor packaging",
    },
]

# Device archetype definitions exhibiting genuine schema polymorphism
ARCHETYPES = [
    {
        "prefix": "DEV-CNC",
        "name": "5-Axis CNC Mill",
        "type": "CNC_MILL",
        "zoneId": "ZONE-MACHINING-B",
        "capabilities": ["vibration", "temperature", "pressure", "spindle_rpm"],
        "specs": {"spindlePowerKw": 15.0, "maxRpm": 12000, "coolantType": "Synthetic Emulsion", "axisCount": 5},
    },
    {
        "prefix": "DEV-PUMP",
        "name": "Hydraulic Pressure Pump",
        "type": "VIBRATION_SENSOR",
        "zoneId": "ZONE-MACHINING-B",
        "capabilities": ["vibration", "pressure", "flow_rate"],
        "specs": {"pumpDisplacementCc": 250, "maxBar": 350, "motorRatingKw": 22.0},
    },
    {
        "prefix": "DEV-AGV",
        "name": "Autonomous Guided Vehicle (AGV)",
        "type": "AGV_FORKLIFT",
        "zoneId": "ZONE-LOGISTICS-C",
        "capabilities": ["gps_speed", "battery", "location", "motor_temp"],
        "specs": {"payloadCapacityKg": 1500, "batteryTech": "LiFePO4", "navSystem": "LiDAR SLAM"},
    },
    {
        "prefix": "DEV-PDU",
        "name": "Primary Power Distribution Unit",
        "type": "POWER_TRANSFORMER",
        "zoneId": "ZONE-ENERGY-D",
        "capabilities": ["voltage", "current", "power_factor", "energy_kwh"],
        "specs": {"ratedKva": 750, "phases": 3, "nominalVoltage": 400, "cooling": "Forced Air"},
    },
    {
        "prefix": "DEV-HVAC",
        "name": "Industrial Chiller & Air Handler",
        "type": "HVAC_CHILLER",
        "zoneId": "ZONE-CLEANROOM-E",
        "capabilities": ["temperature", "humidity", "refrigerant_pressure", "airflow"],
        "specs": {"coolingTons": 80, "refrigerant": "R-134a", "filterStage": "HEPA H14"},
    },
    {
        "prefix": "DEV-CLEAN",
        "name": "Cleanroom Particle Analyzer",
        "type": "CLEANROOM_MONITOR",
        "zoneId": "ZONE-CLEANROOM-E",
        "capabilities": ["temperature", "humidity", "particulate_ppm", "air_velocity"],
        "specs": {"isoStandard": "ISO Class 5", "laserSource": "Diode 780nm"},
    },
]


def generate_devices():
    devices = []
    device_counter = 1

    for archetype in ARCHETYPES:
        # Generate 10 devices per archetype = 60 total devices
        for i in range(1, 11):
            dev_id = f"{archetype['prefix']}-{i:03d}"
            # Small random geospatial offset around plant floor
            lng = round(BASE_LNG + random.uniform(-0.002, 0.002), 6)
            lat = round(BASE_LAT + random.uniform(-0.002, 0.002), 6)

            status = "ONLINE"
            if dev_id == "DEV-CNC-004":
                status = "WARNING"  # Pre-configured failure progression
            elif dev_id == "DEV-AGV-007":
                status = "CRITICAL"

            device_doc = {
                "deviceId": dev_id,
                "name": f"{archetype['name']} #{i:02d}",
                "type": archetype["type"],
                "zoneId": archetype["zoneId"],
                "status": status,
                "capabilities": archetype["capabilities"],
                "specs": archetype["specs"],
                "location": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
                "installedAt": datetime.now(timezone.utc) - timedelta(days=random.randint(60, 500)),
                "lastSeen": datetime.now(timezone.utc),
                "firmwareVersion": f"v{random.randint(2, 4)}.{random.randint(0, 9)}",
            }
            devices.append(device_doc)
            device_counter += 1

    return devices


def generate_readings_for_device(dev, ts, is_faulty_run=False, fault_step=0.0):
    """Generates polymorphic readings matching device capabilities."""
    dev_type = dev["type"]
    readings = {}
    errors = []
    status = "OK"

    if dev_type == "CNC_MILL":
        # Normal baseline: vibration 1.2-2.5 mm/s, temp 40-58 C
        if is_faulty_run:
            # Vibration ramp fault progression (Query 2 trigger)
            vibe = round(2.5 + (fault_step * 12.0) + random.uniform(-0.3, 0.5), 2)
            temp = round(52.0 + (fault_step * 45.0) + random.uniform(-1.0, 1.5), 1)
            press = round(6.5 + random.uniform(-0.2, 0.2), 2)
            rpm = int(8500 + random.uniform(-150, 150))
            if vibe > 8.0:
                errors.append("ERR_VIBRATION_HARMONIC_EXCEEDED")
                status = "CRITICAL" if vibe > 11.0 else "WARNING"
        else:
            vibe = round(random.gauss(1.8, 0.3), 2)
            temp = round(random.gauss(48.0, 3.5), 1)
            press = round(random.gauss(6.8, 0.15), 2)
            rpm = int(random.gauss(9200, 200))

        readings = {
            "vibration_mms": max(0.1, vibe),
            "temperature_c": temp,
            "pressure_bar": max(0.0, press),
            "spindle_rpm": rpm,
        }

    elif dev_type == "AGV_FORKLIFT":
        # AGV readings: speed, battery %, location, motor temp
        if is_faulty_run:
            battery = round(max(2.0, 18.0 - (fault_step * 15.0)), 1)
            motor_temp = round(65.0 + (fault_step * 25.0), 1)
            errors.append("ERR_BATTERY_CRITICAL_DISCHARGE")
            status = "CRITICAL"
        else:
            battery = round(random.uniform(45.0, 98.0), 1)
            motor_temp = round(random.gauss(42.0, 4.0), 1)

        readings = {
            "gps_speed_kph": round(random.uniform(0.0, 8.5), 1),
            "battery_pct": battery,
            "motor_temp_c": motor_temp,
            "heading_deg": random.randint(0, 359),
        }

    elif dev_type == "POWER_TRANSFORMER":
        if is_faulty_run:
            # Overvoltage spike anomaly (Query 1 trigger)
            voltage = round(478.0 + random.uniform(5.0, 15.0), 1)
            current = round(340.0 + random.uniform(10.0, 40.0), 1)
            errors.extend(["ERR_OVERVOLTAGE_SURGE", "ERR_THYRISTOR_GATE_TRIP"])
            status = "CRITICAL"
        else:
            voltage = round(random.gauss(400.0, 3.0), 1)
            current = round(random.gauss(185.0, 15.0), 1)

        readings = {
            "voltage_v": voltage,
            "current_a": current,
            "power_factor": round(random.uniform(0.92, 0.98), 2),
            "energy_kwh": round(random.uniform(12000.0, 15000.0), 1),
        }

    elif dev_type == "HVAC_CHILLER":
        readings = {
            "temperature_c": round(random.gauss(21.5, 0.8), 2),
            "humidity_rh": round(random.gauss(44.0, 2.5), 1),
            "refrigerant_pressure_psi": round(random.gauss(115.0, 4.0), 1),
            "airflow_cfm": round(random.gauss(3200.0, 80.0), 0),
        }

    elif dev_type == "CLEANROOM_MONITOR":
        readings = {
            "temperature_c": round(random.gauss(20.0, 0.4), 2),
            "humidity_rh": round(random.gauss(40.0, 1.2), 1),
            "particulate_ppm": round(max(0.5, random.gauss(2.1, 0.6)), 2),
            "air_velocity_ms": round(random.gauss(0.45, 0.03), 2),
        }

    else:
        # Generic hydraulic vibration pump
        readings = {
            "vibration_mms": round(random.gauss(2.2, 0.4), 2),
            "pressure_bar": round(random.gauss(180.0, 8.0), 1),
            "flow_rate_lpm": round(random.gauss(45.0, 2.0), 1),
        }

    return readings, errors, status


def seed_database():
    """Populates collections with zones, polymorphic devices, and time-series events."""
    setup_schema_and_indexes()
    db = get_db()

    print("\n--- Seeding Initial Digital Twin Data ---")

    # 1. Seed Zones
    db.zones.delete_many({})
    db.zones.insert_many(ZONES)
    print(f"Seeded {len(ZONES)} factory zones.")

    # 2. Seed Devices
    devices = generate_devices()
    db.devices.delete_many({})
    db.devices.insert_many(devices)
    print(f"Seeded {len(devices)} polymorphic IoT devices.")

    # 3. Seed Events (Historical telemetry over past 24 hours)
    db.events.delete_many({})
    events_batch = []
    now = datetime.now(timezone.utc)

    print("Generating 24-hour time-series telemetry with pre-injected anomaly signatures...")

    # We generate snapshots every 15 minutes for 24 hours = 96 points per device
    time_points = [now - timedelta(minutes=15 * step) for step in range(95, -1, -1)]

    for dev in devices:
        is_failing_cnc = dev["deviceId"] == "DEV-CNC-004"
        is_spiking_pdu = dev["deviceId"] == "DEV-PDU-002"
        is_draining_agv = dev["deviceId"] == "DEV-AGV-007"

        for idx, ts in enumerate(time_points):
            # Calculate fault progression step (0.0 = normal, 1.0 = full fault at recent end)
            progress = idx / float(len(time_points) - 1)

            if is_failing_cnc and progress > 0.4:
                # Progressive bearing degradation
                readings, errors, status = generate_readings_for_device(
                    dev, ts, is_faulty_run=True, fault_step=(progress - 0.4) / 0.6
                )
            elif is_spiking_pdu and (len(time_points) - 10 <= idx <= len(time_points) - 6):
                # Temporary voltage surge episode
                readings, errors, status = generate_readings_for_device(dev, ts, is_faulty_run=True, fault_step=1.0)
            elif is_draining_agv and idx >= len(time_points) - 12:
                # Critical battery drainage
                readings, errors, status = generate_readings_for_device(dev, ts, is_faulty_run=True, fault_step=0.9)
            else:
                readings, errors, status = generate_readings_for_device(dev, ts, is_faulty_run=False)

            event_doc = {
                "deviceId": dev["deviceId"],
                "ts": ts,
                "readings": readings,
                "status": status,
                "errors": errors,
            }
            events_batch.append(event_doc)

            # Insert in chunks of 1000 for high performance
            if len(events_batch) >= 1000:
                db.events.insert_many(events_batch)
                events_batch = []

    if events_batch:
        db.events.insert_many(events_batch)

    total_events = db.events.count_documents({})
    print(f"Successfully generated and inserted {total_events} telemetry events.")

    # 4. Seed Alerts
    db.alerts.delete_many({})
    alerts = [
        {
            "alertId": "ALT-001",
            "deviceId": "DEV-CNC-004",
            "ruleId": "RULE_BEARING_VIBRATION",
            "severity": "CRITICAL",
            "message": "Continuous vibration escalation detected on Spindle Axis Z (14.2 mm/s > threshold 7.0 mm/s)",
            "metric": "vibration_mms",
            "value": 14.2,
            "threshold": 7.0,
            "ts": now - timedelta(minutes=18),
            "acknowledged": False,
        },
        {
            "alertId": "ALT-002",
            "deviceId": "DEV-PDU-002",
            "ruleId": "RULE_OVERVOLTAGE_SURGE",
            "severity": "HIGH",
            "message": "Transient high-voltage surge recorded: 488.5 V on Phase B (nominal 400V)",
            "metric": "voltage_v",
            "value": 488.5,
            "threshold": 440.0,
            "ts": now - timedelta(minutes=45),
            "acknowledged": True,
        },
        {
            "alertId": "ALT-003",
            "deviceId": "DEV-AGV-007",
            "ruleId": "RULE_BATTERY_DEPLETED",
            "severity": "HIGH",
            "message": "AGV battery depleted below safe return threshold: 4.8% remaining",
            "metric": "battery_pct",
            "value": 4.8,
            "threshold": 15.0,
            "ts": now - timedelta(minutes=65),
            "acknowledged": False,
        },
    ]
    db.alerts.insert_many(alerts)
    print(f"Seeded {len(alerts)} initial alert incident records.")

    # 5. Seed login accounts (passwords come from .env; stored only as salted hashes)
    from app.auth import ensure_user
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    viewer_user = os.getenv("VIEWER_USERNAME", "viewer")
    viewer_pass = os.getenv("VIEWER_PASSWORD", "")
    if admin_pass and viewer_pass:
        db.users.delete_many({})
        ensure_user(db, admin_user, admin_pass, "admin")
        ensure_user(db, viewer_user, viewer_pass, "viewer")
        print(f"Seeded login accounts: '{admin_user}' (admin), '{viewer_user}' (viewer).")
    else:
        print("WARNING: ADMIN_PASSWORD / VIEWER_PASSWORD not set in .env - no login accounts created.")

    print("\n[SUCCESS] Digital Twin seed data completely initialized!")
    return True


if __name__ == "__main__":
    seed_database()
