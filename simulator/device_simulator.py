"""IoT Device Telemetry Simulator & Dynamic Fault Injection Engine

Simulates 50-200 virtual industrial IoT devices generating polymorphic sensor data.
Allows real-time injection of mechanical, thermal, electrical, and sensor faults
for live viva and rubric demonstration.
"""

import sys
import os
import time
import random
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.connection import get_db


class DeviceSimulator:
    def __init__(self, tick_interval: float = 2.0):
        self.tick_interval = tick_interval
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.active_faults: Dict[str, Dict[str, Any]] = {}
        self.total_ticks = 0
        self.events_emitted = 0

    def start(self):
        """Starts simulator background loop in a separate daemon thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[SIMULATOR] Started background telemetry generator (tick: {self.tick_interval}s)")

    def stop(self):
        """Stops the simulator loop."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        print("[SIMULATOR] Simulator stopped.")

    def inject_fault(self, device_id: str, fault_type: str, severity: str = "HIGH", notes: str = ""):
        """Injects an intentional operational fault onto a targeted device.
        Fault types:
        - 'vibration_ramp': progressive mechanical bearing failure
        - 'temperature_spike': overheating / cooling loop breakdown
        - 'battery_drain': critical battery depletion (AGV fleet)
        - 'voltage_surge': severe overvoltage electrical transient
        - 'sensor_errors': intermittent device hardware/driver errors
        """
        self.active_faults[device_id] = {
            "type": fault_type,
            "severity": severity,
            "step": 0,
            "injected_at": datetime.now(timezone.utc),
            "notes": notes,
        }
        print(f"[SIMULATOR] INJECTED FAULT [{fault_type.upper()}] on {device_id} (Severity: {severity})")
        return {"status": "injected", "deviceId": device_id, "faultType": fault_type}

    def clear_fault(self, device_id: str):
        """Removes any active injected fault from a device."""
        if device_id in self.active_faults:
            del self.active_faults[device_id]
            print(f"[SIMULATOR] Cleared fault on {device_id}")
            return {"status": "cleared", "deviceId": device_id}
        return {"status": "not_found", "deviceId": device_id}

    def clear_all_faults(self):
        """Clears all active faults across all devices."""
        count = len(self.active_faults)
        self.active_faults.clear()
        return {"status": "all_cleared", "count": count}

    def _generate_telemetry(self, dev: dict) -> dict:
        dev_id = dev["deviceId"]
        dev_type = dev.get("type", "CNC_MILL")
        now = datetime.now(timezone.utc)

        fault = self.active_faults.get(dev_id)
        fault_type = fault["type"] if fault else None
        if fault:
            fault["step"] += 1
            step = min(fault["step"], 30)
        else:
            step = 0

        readings = {}
        errors = []
        status = "OK"

        if dev_type == "CNC_MILL":
            # Normal baseline: vibe 1.5 - 2.5 mm/s, temp 45 - 55 C
            vibe = round(random.gauss(1.8, 0.25), 2)
            temp = round(random.gauss(48.0, 3.0), 1)
            press = round(random.gauss(6.8, 0.2), 2)
            rpm = int(random.gauss(9200, 150))

            if fault_type == "vibration_ramp":
                vibe = round(2.0 + (step * 0.45) + random.uniform(0.1, 0.8), 2)
                temp = round(48.0 + (step * 1.5) + random.uniform(-0.5, 1.0), 1)
                if vibe > 7.0:
                    errors.append("ERR_VIBRATION_HARMONIC_EXCEEDED")
                    status = "CRITICAL" if vibe > 10.0 else "WARNING"

            elif fault_type == "temperature_spike":
                temp = round(85.0 + random.uniform(5.0, 18.0), 1)
                errors.append("ERR_THERMAL_RUNAWAY_LIMIT")
                status = "CRITICAL"

            readings = {
                "vibration_mms": max(0.1, vibe),
                "temperature_c": temp,
                "pressure_bar": max(0.1, press),
                "spindle_rpm": rpm,
            }

        elif dev_type == "AGV_FORKLIFT":
            battery = round(random.uniform(50.0, 95.0), 1)
            motor_temp = round(random.gauss(38.0, 3.0), 1)

            if fault_type == "battery_drain":
                battery = round(max(2.0, 12.0 - (step * 0.4)), 1)
                errors.append("ERR_BATTERY_CRITICAL_DISCHARGE")
                status = "CRITICAL"

            readings = {
                "gps_speed_kph": round(random.uniform(0.0, 6.5), 1),
                "battery_pct": battery,
                "motor_temp_c": motor_temp,
                "heading_deg": random.randint(0, 359),
            }

        elif dev_type == "POWER_TRANSFORMER":
            voltage = round(random.gauss(400.0, 2.5), 1)
            current = round(random.gauss(190.0, 10.0), 1)

            if fault_type == "voltage_surge":
                voltage = round(470.0 + random.uniform(10.0, 30.0), 1)
                current = round(320.0 + random.uniform(15.0, 35.0), 1)
                errors.extend(["ERR_OVERVOLTAGE_SURGE", "ERR_THYRISTOR_GATE_TRIP"])
                status = "CRITICAL"

            readings = {
                "voltage_v": voltage,
                "current_a": current,
                "power_factor": round(random.uniform(0.93, 0.98), 2),
                "energy_kwh": round(random.uniform(12000.0, 15000.0), 1),
            }

        elif dev_type == "HVAC_CHILLER":
            readings = {
                "temperature_c": round(random.gauss(21.0, 0.6), 2),
                "humidity_rh": round(random.gauss(45.0, 2.0), 1),
                "refrigerant_pressure_psi": round(random.gauss(115.0, 3.0), 1),
                "airflow_cfm": round(random.gauss(3200.0, 50.0), 0),
            }

        else:
            readings = {
                "temperature_c": round(random.gauss(20.0, 0.3), 2),
                "humidity_rh": round(random.gauss(40.0, 1.0), 1),
                "particulate_ppm": round(max(0.2, random.gauss(1.8, 0.4)), 2),
                "air_velocity_ms": round(random.gauss(0.45, 0.02), 2),
            }

        if fault_type == "sensor_errors":
            errors.append("ERR_SENSOR_ADC_OUT_OF_BOUNDS")
            status = "WARNING"

        event_doc = {
            "deviceId": dev_id,
            "ts": now,
            "readings": readings,
            "status": status,
            "errors": errors,
        }
        return event_doc

    def tick_once(self) -> int:
        """Executes one simulation tick across registered devices."""
        db = get_db()
        devices = list(db.devices.find({"status": {"$ne": "DECOMMISSIONED"}}))
        if not devices:
            return 0

        batch = []
        now = datetime.now(timezone.utc)
        alerts_to_create = []

        for dev in devices:
            event = self._generate_telemetry(dev)
            batch.append(event)

            # Generate alerts for critical events
            if event["status"] in ["CRITICAL", "WARNING"] or event["errors"]:
                dev_id = dev["deviceId"]
                # Avoid alert flooding: check if recent alert in last 10 mins
                recent = db.alerts.find_one({"deviceId": dev_id, "acknowledged": False})
                if not recent:
                    reason = ", ".join(event["errors"]) if event["errors"] else f"Status: {event['status']}"
                    alerts_to_create.append({
                        "alertId": f"ALT-{int(now.timestamp())}-{dev_id[-3:]}",
                        "deviceId": dev_id,
                        "ruleId": "RULE_SIM_AUTO",
                        "severity": "CRITICAL" if event["status"] == "CRITICAL" else "HIGH",
                        "message": f"Anomaly on {dev.get('name', dev_id)}: {reason}",
                        "metric": list(event["readings"].keys())[0] if event["readings"] else "status",
                        "value": list(event["readings"].values())[0] if event["readings"] else 0,
                        "ts": now,
                        "acknowledged": False,
                    })

        if batch:
            db.events.insert_many(batch)
            self.events_emitted += len(batch)

        if alerts_to_create:
            db.alerts.insert_many(alerts_to_create)

        self.total_ticks += 1
        return len(batch)

    def _run_loop(self):
        while self.is_running:
            try:
                self.tick_once()
            except Exception as e:
                print(f"[SIMULATOR ERROR] {e}")
            time.sleep(self.tick_interval)


# Global simulator instance
simulator_instance = DeviceSimulator()

if __name__ == "__main__":
    sim = DeviceSimulator(tick_interval=2.0)
    print("Starting standalone simulator CLI for 10 seconds...")
    sim.inject_fault("DEV-CNC-001", "vibration_ramp")
    sim.start()
    time.sleep(10)
    sim.stop()
    print(f"Finished. Total events generated: {sim.events_emitted}")
