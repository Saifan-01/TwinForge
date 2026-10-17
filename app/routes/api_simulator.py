"""Simulator Control API endpoints for live viva demonstration."""

from flask import Blueprint, request, jsonify
from simulator.device_simulator import simulator_instance

bp = Blueprint("simulator", __name__, url_prefix="/api/simulator")


@bp.route("/status", methods=["GET"])
def get_status():
    """Returns simulator running state, active fault injections, and stats."""
    return jsonify({
        "isRunning": simulator_instance.is_running,
        "tickInterval": simulator_instance.tick_interval,
        "totalTicks": simulator_instance.total_ticks,
        "eventsEmitted": simulator_instance.events_emitted,
        "activeFaults": simulator_instance.active_faults,
    })


@bp.route("/start", methods=["POST"])
def start_simulator():
    """Starts the real-time background simulation feed."""
    simulator_instance.start()
    return jsonify({"message": "Simulator started", "isRunning": True})


@bp.route("/stop", methods=["POST"])
def stop_simulator():
    """Stops the real-time background simulation feed."""
    simulator_instance.stop()
    return jsonify({"message": "Simulator stopped", "isRunning": False})


@bp.route("/inject", methods=["POST"])
def inject_fault():
    """Injects an intentional operational fault onto a device for live demo."""
    data = request.get_json() or {}
    device_id = data.get("deviceId")
    fault_type = data.get("faultType", "vibration_ramp")
    severity = data.get("severity", "CRITICAL")
    notes = data.get("notes", "Live injected demo fault")

    if not device_id:
        return jsonify({"error": "Missing 'deviceId'"}), 400

    result = simulator_instance.inject_fault(device_id, fault_type, severity=severity, notes=notes)
    return jsonify(result)


@bp.route("/clear", methods=["POST"])
def clear_fault():
    """Clears injected faults."""
    data = request.get_json() or {}
    device_id = data.get("deviceId")

    if device_id:
        result = simulator_instance.clear_fault(device_id)
    else:
        result = simulator_instance.clear_all_faults()

    return jsonify(result)
