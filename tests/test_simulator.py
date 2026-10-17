"""Tests for the device simulator and fault injection engine."""

import pytest
from simulator.device_simulator import DeviceSimulator


def test_simulator_tick_generation():
    """Verifies that a simulator tick generates telemetry for all registered devices."""
    sim = DeviceSimulator(tick_interval=1.0)
    generated = sim.tick_once()
    assert generated >= 50


def test_fault_injection_and_clearing():
    """Verifies fault injection on a target device and subsequent clearing."""
    sim = DeviceSimulator()
    target_dev = "DEV-CNC-002"

    # Inject vibration ramp
    res = sim.inject_fault(target_dev, "vibration_ramp", severity="CRITICAL")
    assert res["status"] == "injected"
    assert target_dev in sim.active_faults
    assert sim.active_faults[target_dev]["type"] == "vibration_ramp"

    # Generate tick with fault active
    sim.tick_once()
    assert sim.active_faults[target_dev]["step"] > 0

    # Clear fault
    clear_res = sim.clear_fault(target_dev)
    assert clear_res["status"] == "cleared"
    assert target_dev not in sim.active_faults
