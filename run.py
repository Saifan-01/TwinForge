"""Entry point for IoT Digital Twin Flask Server."""

import os
from app import create_app
from simulator.device_simulator import simulator_instance

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # Optional auto-start simulator for immediate live demo
    auto_start = os.getenv("AUTO_START_SIMULATOR", "false").lower() == "true"
    if auto_start:
        simulator_instance.start()

    print(f"\n=======================================================")
    print(f"  INDUSTRIAL IoT DIGITAL TWIN DASHBOARD & REST API")
    print(f"  Access console at: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=debug)
