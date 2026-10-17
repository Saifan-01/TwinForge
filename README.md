# TwinForge: Industrial IoT Digital Twin & Predictive Anomaly Analytics

An industrial-grade IoT Digital Twin platform for smart factories, automated warehouses, and critical infrastructure. Built on **MongoDB Community / Atlas** (WiredTiger) with a **Python Flask REST API** and interactive **Real-Time Plant Command Dashboard**.

---

## 📋 Rubric Mapping (8/8 Criteria Covered)

| Criterion | What is Demonstrated in this Codebase |
| :--- | :--- |
| **1. Problem Identification** | Unplanned industrial downtime ($50B/year problem). Operators need anomaly and failure visibility across 50-200 heterogeneous, non-uniform devices. |
| **2. NoSQL Selection** | Rigorous justification of MongoDB over Relational (RDBMS). Eliminates sparse 100-column NULL tables and the slow EAV anti-pattern. Native polymorphic documents, high-throughput writes, and columnar time-series storage. |
| **3. Data Modeling** | Four core collections: `devices` (polymorphic registry + 2dsphere location), `events` (native time-series + TTL retention), `alerts` (anomaly incidents), and `zones` (spatial plant hierarchy). |
| **4. CRUD Operations** | Add, edit, decommission and delete devices from the Devices page (or the REST API), telemetry ingestion (single and batch), and alert acknowledgment. |
| **5. Advanced NoSQL Features** | `$setWindowFields` rolling statistical Z-score calculations, multi-metric trend prediction pipelines, compound indexes, partial indexes, 2dsphere geospatial index, TTL auto-expiration, and `$jsonSchema` validation rules. |
| **6. Integration** | Modular Flask REST API + modern Dark-Mode Real-Time Digital Twin Dashboard with spatial plant map, live telemetry stream, and query visualizers. |
| **7. Testing & Security** | Login with roles (admin / read-only viewer), API-key access for scripts, CSRF header and login lockout, enforced `$jsonSchema` validation plus API input validation, and an automated `pytest` suite (`tests/`). |
| **8. Demo & Viva** | Multi-device telemetry simulator with on-demand fault injection (vibration ramp, thermal spike, battery drain, voltage surge), plus `docs/report.md`. |

---

## 🏗️ System Architecture

```
+-------------------------------------------------------------------------+
|                  DIGITAL TWIN WEB DASHBOARD (HTML5/CSS3/JS)             |
|  - Spatial Plant Map    - Telemetry Stream      - Anomaly Explorer      |
|  - Query 1 Visualizer   - Query 2 Risk Board    - Live Fault Lab        |
+------------------------------------+------------------------------------+
                                     | HTTP / REST API
                                     v
+------------------------------------+------------------------------------+
|                         FLASK APPLICATION CORE                         |
|  - /api/devices (CRUD + Geo)            - /api/events (Ingest & Feed)   |
|  - /api/analytics (Queries 1 & 2)       - /api/simulator (Fault Engine) |
+------------------------------------+------------------------------------+
                                     | PyMongo Driver
                                     v
+------------------------------------+------------------------------------+
|                MONGODB (COMMUNITY 9.0 / ATLAS CLOUD)                    |
|  - devices: 2dsphere GeoJSON            - events: Native Time-Series    |
|  - alerts: Incident Indexing            - zones: Plant Spatial Grid     |
|  - $jsonSchema Validation Rules         - 7-Day Automatic TTL Policy    |
+-------------------------------------------------------------------------+
```

---

## ⚡ Quickstart Guide (Run in 2 Minutes)

### Step 1: Create a virtual environment
```powershell
cd iot-digital-twin
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(Windows CMD: `venv\Scripts\activate.bat` | Linux/macOS: `source venv/bin/activate`)*

### Step 2: Install dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Configure `.env`
Copy `.env.example` to `.env`, then set `API_KEY`, `SECRET_KEY`, `ADMIN_PASSWORD` and `VIEWER_PASSWORD` to your own values (and `MONGO_URI` if you use Atlas).

### Step 4: Seed the database
Make sure MongoDB is running (local) or your Atlas URI is in `.env`, then:
```powershell
# Creates collections, indexes and validation rules, seeds zones, devices,
# 5,700+ events, alerts, and the admin / viewer login accounts
python db/seed_data.py
```

### Step 5: Run the application
```powershell
python run.py
```
Open **http://127.0.0.1:5000** and log in with the admin or viewer account from your `.env`.

### Step 6: Run tests and the index benchmark
```powershell
pytest -v
pytest -v > docs/test_results.txt   # save the evidence for the report
python scripts/benchmark_indexes.py
```

### API access for scripts
Send the `API_KEY` from `.env` in the `X-API-Key` header, for example:
```bash
curl -H "X-API-Key: <your key>" http://127.0.0.1:5000/api/devices
```

---

## 🔍 The Two Topic Analytical Queries

### Query 1: "Show me everything unusual that happened in the factory today"
- **Implementation**: [`queries/unusual_events.py`](queries/unusual_events.py) & [`queries/unusual_events.js`](queries/unusual_events.js)
- **Mechanism**:
  - Uses `$setWindowFields` partitioned by `deviceId` to compute rolling mean ($\mu$) and sample standard deviation ($\sigma$) across a sliding window of recent readings.
  - Computes the statistical Z-Score: $Z = \frac{|x - \mu|}{\sigma}$.
  - Flags events where $Z \ge 2.5$ or where hardware error codes exist (`errors.0: { $exists: true }`).

### Query 2: "Which machines show signs of failure?"
- **Implementation**: [`queries/failure_prediction.py`](queries/failure_prediction.py) & [`queries/failure_prediction.js`](queries/failure_prediction.js)
- **Mechanism**:
  - Multi-variate trend correlation pipeline scanning over recent telemetry.
  - Correlates rising vibration with ascending temperatures:
    $$\Delta_{\text{vibe}} = \text{maxVibe} - \text{firstVibe}$$
    $$\Delta_{\text{temp}} = \text{maxTemp} - \text{firstTemp}$$
  - Computes a composite Failure Risk Score ($0 \le S \le 100$) combining vibration, thermal, battery depletion, and error code occurrences.
  - Ranks machines by failure urgency descending (`$sort: { failureRiskScore: -1 }`).

---

## 🧪 Live Demonstration & Viva Guide

1. Log in at `http://127.0.0.1:5000` as the admin user.
2. **Polymorphic data**: open **Devices** and **Live readings**. CNC mills report vibration, temperature, pressure and RPM; AGVs report battery, speed and heading; transformers report voltage, current and energy. One collection holds all of them with no schema change.
3. **CRUD**: on **Devices**, add a device with its own sensor list, edit it, decommission it, then delete it.
4. **Query 1**: open **Unusual today**. Explain how `$setWindowFields` computes the rolling mean and standard deviation and flags |z| of 2.5 or more, and how error codes are flagged separately.
5. **Query 2**: open **Failure risk**. Show the ranked machines and explain how the score combines vibration and temperature trends, battery and errors.
6. **Live fault injection**: open **Fault lab**, start a vibration ramp on `DEV-CNC-001`, click **Start live readings**, then watch its score climb on **Failure risk**.
7. **Access control**: log in as the viewer account and show that edit, delete and fault controls are not available (the API also returns 403).
8. **Index performance**: show the measured results and explain what they show. Quote only the numbers from your own run of `scripts/benchmark_indexes.py`.

---

## 📦 How to Create the Submission Zip

To submit this project to your college portal, you can run the automated packaging script:

```powershell
python scripts/package_project.py
```

This creates a clean, lightweight `iot-digital-twin.zip` next to the project folder. It automatically excludes:
- `venv/` and `.venv/` (avoids bloating the zip by 100+ MB)
- `__pycache__/` and `*.pyc`
- `.git/`
- `.env` (protects secrets; preserves `.env.example`)
- Temporary log files

### Manual Zip on Windows (Alternative)
1. Right-click the `iot-digital-twin` folder → **Send to** → **Compressed (zipped) folder**.
2. Make sure you delete the `venv` directory first if doing manual zipping, or follow the automated script above.

---

## 📁 Project Directory Structure

```
iot-digital-twin/
├── README.md                      # Comprehensive project guide & rubric mapping
├── requirements.txt               # Python package dependencies
├── pytest.ini                     # Pytest configuration
├── .env.example                   # Environment configuration template
├── .env                           # Local connection configuration
├── .gitignore                     # Git and zip exclusion rules
├── run.py                         # Web application entry point
├── app/                           # Flask REST API & Digital Twin Dashboard
│   ├── __init__.py                # App factory
│   ├── auth.py                    # Login, roles, API key, CSRF guard, lockout
│   ├── utils.py                   # BSON / JSON serialization
│   ├── routes/                    # Modular API route controllers
│   │   ├── api_devices.py         # Device CRUD + 2dsphere geospatial
│   │   ├── api_events.py          # High-throughput event ingestion
│   │   ├── api_analytics.py       # Queries 1 & 2 analytics endpoints
│   │   ├── api_alerts.py          # Incident alert lifecycle
│   │   ├── api_simulator.py       # Simulator control & fault injection
│   │   └── views.py               # Dashboard view router
│   ├── static/                    # Dashboard UI assets (CSS & JS)
│   └── templates/                 # dashboard.html, login.html
├── db/                            # Database Layer
│   ├── connection.py              # MongoDB connection manager (Atlas / Local)
│   ├── schema_validation.js       # $jsonSchema validation rules
│   ├── indexes.js                 # 2dsphere, compound, partial, TTL indexes (mongosh)
│   ├── setup_indexes.py           # Programmatic collection & index creator
│   └── seed_data.py               # Seeds 5 zones, 60 devices, 5,700+ events
├── queries/                       # Rubric Core Analytical Queries
│   ├── unusual_events.py          # Query 1: $setWindowFields Z-score outlier pipeline
│   ├── unusual_events.js          # Query 1 mongosh script
│   ├── failure_prediction.py      # Query 2: Predictive failure trend pipeline
│   └── failure_prediction.js      # Query 2 mongosh script
├── simulator/                     # Device Simulator Engine
│   └── device_simulator.py        # 50+ virtual IoT devices + fault injection
├── tests/                         # Pytest Automated Test Suite
│   ├── conftest.py                # Fixtures and test client setup
│   ├── test_auth.py               # Authentication, roles and validation tests
│   ├── test_devices.py            # Device CRUD & Geospatial tests
│   ├── test_events.py             # Polymorphic event ingestion tests
│   ├── test_queries.py            # Query 1 & Query 2 verification tests
│   └── test_simulator.py          # Simulation & fault engine tests
├── scripts/                       # Maintenance & Packaging Scripts
│   ├── benchmark_indexes.py       # Criterion 5 index benchmark runner
│   └── package_project.py         # One-click clean submission zip packager
└── docs/                          # Technical Documentation & Evidence
    ├── report.md                  # Comprehensive academic/technical report
    ├── benchmark_results.md       # Machine-generated benchmark evidence
    └── test_results.txt           # Saved pytest execution logs
```
