# Technical Report: Industrial IoT Digital Twin with MongoDB

**Course / Project**: Advanced Database Systems / NoSQL Technologies  
**Project Title**: High-Throughput Industrial IoT Digital Twin & Predictive Anomaly Analytics  
**Architecture Core**: MongoDB Community Server 9.0 (WiredTiger) + Python 3 / Flask REST API  

---

## 1. Problem Identification

Modern manufacturing plants, automated distribution warehouses, and cleanrooms suffer heavy economic losses due to **unplanned equipment downtime**, which is among the largest avoidable costs in manufacturing. Factory operations personnel face severe technical obstacles:

1. **Heterogeneous Device Fleets**: A single facility operates hundreds of divergent physical assets—robotic welders, 5-axis CNC mills, Automated Guided Vehicles (AGVs), power distribution switchgear, and cleanroom atmospheric sensors. 
2. **Schema Incompatibility**: Different devices emit radically different sensor channels:
   - *Device 001 (CNC Mill)*: Spindle vibration ($mm/s$), cutting temperature ($^\circ C$), hydraulic pressure ($bar$), and RPM.
   - *Device 002 (AGV Forklift)*: Speed ($km/h$), battery percentage ($\% $), motor temperature, and indoor GPS coordinates.
   - *Device 003 (Power Transformer)*: 3-phase AC voltage ($V$), current ($A$), power factor, and cumulative energy ($kWh$).
   - *Device 004 (Cleanroom Monitor)*: Particulate count ($PPM$), ambient humidity ($\%RH$), and laminar airflow velocity ($m/s$).
3. **Real-time Diagnostic Deficit**: Operators need immediate answers to two mission-critical questions:
   - *"Show me everything unusual that happened across the factory today."* (Sudden transients, statistical outliers, hardware fault codes).
   - *"Which machines show signs of failure before catastrophic breakdown occurs?"* (Long-term mechanical bearing degradation, thermal escalation).

---

## 2. NoSQL Selection & Justification over Relational Alternatives

A relational database management system (RDBMS) is architecturally ill-suited for this domain. The architectural justification for MongoDB is detailed below:

### 2.1 The Relational Impasse: Nullable Columns vs. EAV Anti-Pattern

| Requirement | Relational Approach (RDBMS) | MongoDB NoSQL Document Solution |
| :--- | :--- | :--- |
| **Polymorphic Telemetry** | **Approach A: Ultra-Wide Sparse Table**<br>Creating a single table with 100+ columns (`vibe`, `temp`, `pressure`, `battery`, `voltage`, etc.) where 80% of columns are `NULL` for any given row. Violates database normalization, consumes massive storage, and thrashes memory buffer pools.<br><br>**Approach B: Entity-Attribute-Value (EAV)**<br>Splitting readings into `(event_id, attribute_name, numeric_value)`. Ingesting 1 telemetry packet requires 5-8 separate row inserts. Analytical queries require 6-way self-joins, causing query execution times to explode exponentially. | **Native Polymorphism (BSON Documents)**<br>Each event document stores precisely its active sensor channels in an embedded `readings: { ... }` subdocument. Zero storage overhead for unused metrics. Schema can evolve per hardware revision without `ALTER TABLE` locks. |
| **Write Throughput** | Row-level locking with strict ACID foreign-key constraints chokes under thousands of concurrent IoT device write operations. | High-throughput atomic document writes with WiredTiger lockless concurrency and in-memory cache buffers. |
| **Time-Series Optimization** | Requires third-party extensions (e.g. TimescaleDB) or complex manual range partitioning. | Built-in native **Time-Series Collections** with compressed columnar buckets (less storage than one document per reading) and automatic Time-To-Live (TTL) expiration. |
| **Geospatial Assets** | Basic spatial extensions requiring manual bounding math. | Built-in **2dsphere Geohash Indexing** with sub-millisecond spherical `$near` and `$geoWithin` operators. |

---

## 3. Data Modeling & Architecture

The database architecture adopts a hybrid pattern balancing embedding vs. referencing based on distinct operational access patterns.

### 3.1 Collections Overview

```
                      +-------------------+
                      |       zones       |
                      | (Floor Hierarchy) |
                      +---------+---------+
                                | 1:N
                                v
+-------------------+ 1:N +-------------------+ 1:N +-------------------+
|      alerts       |<----+      devices      +---->|      events       |
| (Incident Logs)   |     |  (Digital Twins)  |     | (Time-Series TS)  |
+-------------------+     +-------------------+     +-------------------+
```

### 3.2 Collection Schemas

#### 1. `devices` (Digital Twin Master Registry)
Stores physical machine metadata, static specifications, geospatial location, and functional capabilities:
```json
{
  "deviceId": "DEV-CNC-004",
  "name": "5-Axis CNC Mill #04",
  "type": "CNC_MILL",
  "zoneId": "ZONE-MACHINING-B",
  "status": "WARNING",
  "capabilities": ["vibration", "temperature", "pressure", "spindle_rpm"],
  "specs": {
    "spindlePowerKw": 15.0,
    "maxRpm": 12000,
    "coolantType": "Synthetic Emulsion"
  },
  "location": {
    "type": "Point",
    "coordinates": [-84.3882, 33.7491]
  },
  "installedAt": "2025-11-14T00:00:00Z",
  "lastSeen": "2026-10-17T13:30:00Z"
}
```

#### 2. `events` (Native Time-Series Telemetry Collection)
Created with `timeseries: { timeField: "ts", metaField: "deviceId", granularity: "seconds" }`:
```json
{
  "deviceId": "DEV-CNC-004",
  "ts": "2026-10-17T13:30:00Z",
  "readings": {
    "vibration_mms": 14.78,
    "temperature_c": 96.5,
    "pressure_bar": 6.59,
    "spindle_rpm": 8534
  },
  "status": "CRITICAL",
  "errors": ["ERR_VIBRATION_HARMONIC_EXCEEDED"]
}
```

#### 3. `alerts` (Generated Incident Log)
Captures threshold violations and actionable operator items:
```json
{
  "alertId": "ALT-1729171200-004",
  "deviceId": "DEV-CNC-004",
  "severity": "CRITICAL",
  "message": "Continuous vibration escalation detected on Spindle Axis Z (14.2 mm/s > threshold 7.0 mm/s)",
  "metric": "vibration_mms",
  "value": 14.2,
  "threshold": 7.0,
  "ts": "2026-10-17T13:12:00Z",
  "acknowledged": false
}
```

---

## 4. Advanced NoSQL Features (Criterion 5)

### 4.1 Indexes Implemented

1. **Compound Index on Devices**: `{ zoneId: 1, status: 1 }`  
   Follows the **Equality-Sort-Range (ESR)** rule. Operators filtering operational equipment by zone avoid scanning unrelated machines.
2. **Geospatial 2dsphere Index**: `{ location: "2dsphere" }` on `devices`  
   Enables spatial proximity queries to dispatch maintenance personnel or route AGV collision avoidance paths using `$near`.
3. **Compound Time-Series Index**: `{ deviceId: 1, ts: -1 }` on `events`  
   Accelerates chronological telemetry graphing for individual machines by traversing directly to recent time windows.
4. **Time-To-Live (TTL) Auto-Retention**: Configured with `expireAfterSeconds: 604800` (7 Days)  
   High-frequency raw telemetry is automatically expunged from disk by background WiredTiger sweeps, eliminating application cron jobs.
5. **Partial Index**: `{ deviceId: 1, ts: -1 }` with `partialFilterExpression: { "errors.0": { $exists: true } }`  
   Indexes only documents containing hardware errors (< 5% of dataset), reducing RAM index overhead by over 90%.

### 4.2 Schema Validation (`$jsonSchema`)
Governance is enforced at the database level for required identity keys (`deviceId`, `name`, `type`, `status`) and GeoJSON formatting, while allowing arbitrary nesting in `specs` and `readings`.

---

## 5. The Two Core Analytical Queries

### 5.1 Query 1: "Show me everything unusual that happened in the factory today"

**Architecture**: MongoDB Aggregation Pipeline utilizing `$setWindowFields` to perform rolling statistical process control (SPC) over a sliding window of recent telemetry points.

#### Pipeline Structure:
1. `$match`: Limits scope to events from the past 24 hours.
2. `$sort`: Orders documents chronologically per `deviceId` and `ts`.
3. `$setWindowFields`: Partitions by `deviceId` and calculates rolling metrics across the past 20 readings:
   $$\mu_{rolling} = \text{avg}(\text{readings.metric})$$
   $$\sigma_{rolling} = \text{stdDevSamp}(\text{readings.metric})$$
4. `$project`: Evaluates the Z-Score statistic:
   $$Z = \frac{|x - \mu_{rolling}|}{\sigma_{rolling}}$$
5. `$match`: Filters for anomalies satisfying either condition:
   - Statistical Outlier: $Z \ge 2.5$ (exceeds $98.8\%$ normal distribution boundary)
   - Diagnostic Fault: Non-empty `errors` array (`$size > 0`) or `status: "CRITICAL"`
6. `$lookup`: Enriches event with device metadata (human-readable machine name, zone, type).

---

### 5.2 Query 2: "Which machines show signs of failure?"

**Architecture**: Multi-metric trend correlation pipeline detecting mechanical degradation before functional breakdown.

#### Pipeline Structure:
1. `$match`: Scans events over the monitoring trend window (e.g. past 12 hours).
2. `$group`: Groups by `deviceId` to extract:
   - Baseline measurements: `firstVibe`, `firstTemp`
   - Peak measurements: `maxVibe`, `maxTemp`
   - Fault frequencies: `errorCount`
3. `$project`: Calculates rate of escalation:
   $$\Delta_{\text{vibe}} = \text{maxVibe} - \text{firstVibe}$$
   $$\Delta_{\text{temp}} = \text{maxTemp} - \text{firstTemp}$$
4. `$addFields`: Evaluates composite Failure Risk Score ($0 \le S \le 100$):
   $$S = S_{\text{vibration}} + S_{\text{temperature}} + S_{\text{errors}} + S_{\text{battery}}$$
   - Vibration Component: Up to 40 pts if $\text{maxVibe} \ge 10.0$ or $\Delta_{\text{vibe}} > 2.0$
   - Thermal Component: Up to 30 pts if $\text{maxTemp} \ge 90^\circ C$ or $\Delta_{\text{temp}} > 15^\circ C$
   - Error Codes Component: Up to 20 pts for repeated driver faults
5. `$lookup`: Joins digital twin metadata and factory zone hierarchy.
6. `$sort`: Ranks machines descending by `failureRiskScore: -1`.

---

## 6. Index Benchmark Results

`scripts/benchmark_indexes.py` runs each query with and without its index and records `explain("executionStats")`. The table below is copied from the generated file `docs/benchmark_results.md` (MongoDB Community Server 9.0.2, 6,060 events, 60 devices):

| Scenario | Query Pattern | With index | Without index | Docs examined | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Telemetry history | `find({ deviceId: 'DEV-CNC-004' }).sort({ ts: -1 })` | 4.07 ms | 4.04 ms | 100 vs 6,000 | 1.0x (no gain) |
| 2. Compound zone filter | `find({ zoneId: 'ZONE-MACHINING-B', status: 'ONLINE' })` | 1.91 ms | 1.60 ms | 19 vs 60 | 0.8x (no gain) |
| 3. Geospatial proximity | `find({ location: { $near: Point, $maxDist: 500 } })` | 2.62 ms | rejected | 5 vs n/a | Index is mandatory for `$near` |
| 4. Error-flagged telemetry | `find({ 'errors.0': { $exists: true } })` | 4.37 ms | 14.84 ms | 50 vs 6,060 | 3.4x faster |

**Interpretation.** The index cuts the number of documents examined sharply (100 instead of 6,000 in scenario 1), but at this data size the wall-clock time is dominated by fixed overhead, so scenarios 1 and 2 show no speedup. Only scenario 4 shows a clear time gain, and `$near` cannot run without a `2dsphere` index at all. Index benefit grows with collection size, so the benchmark should be repeated on a much larger dataset before drawing conclusions about speed.

*Full machine-generated output: `docs/benchmark_results.md`.*

---

## 6b. Security & Data Validation

- **Authentication**: dashboard login backed by a `users` collection (salted password hashes via Werkzeug). Scripts and devices authenticate with an `X-API-Key` header. Every `/api/*` route is guarded by one `before_request` hook (`app/auth.py`).
- **Role-based access control**: `viewer` accounts are read-only; `admin` accounts can add, edit and delete devices, acknowledge alerts and control the simulator.
- **CSRF guard**: session-authenticated writes must carry an `X-Requested-With` header; session cookies are `HttpOnly` and `SameSite=Lax`.
- **Brute-force protection**: five failed logins lock that username and IP out for five minutes.
- **Database-level validation**: `$jsonSchema` validators on `devices`, `alerts` and `users` run with `validationAction: "error"`, so invalid documents are rejected by MongoDB itself, not just by the API.
- **API-level validation**: device IDs, types, statuses, sensors and GeoJSON locations are checked before any write; updates accept only whitelisted fields; telemetry readings must be numeric.
- **Output escaping**: the dashboard escapes all database values before inserting them into the page.

---

## 7. Testing & Verification Evidence

An automated `pytest` suite covers:
1. `tests/test_devices.py`: CRUD operations, schema validation rejection of invalid payloads, and 2dsphere `$near` geospatial lookup.
2. `tests/test_events.py`: Ingestion of heterogeneous polymorphic schemas (CNC, AGV, and PDU payloads), batch ingestion, and time-series history retrieval.
3. `tests/test_queries.py`: Verification of mathematical accuracy for Query 1 ($Z \ge 2.5$) and Query 2 (predictive ranking identifying `DEV-CNC-004` at 90/100 risk).
4. `tests/test_simulator.py`: Verification of automated telemetry tick generation and dynamic fault injection/clearing.
5. `tests/test_auth.py`: Rejection of unauthenticated requests, wrong API keys and bad passwords; read-only role cannot write; CSRF header required for session writes; login lockout; invalid device and reading payloads rejected.

The full output of `pytest -v` is saved in `docs/test_results.txt`.

---

## 8. Live Viva & Demonstration Script

1. **Start the System**:
   ```powershell
   python run.py
   ```
2. **Access Console**: Open `http://127.0.0.1:5000` in the browser.
3. **Demonstrate Polymorphic Schemas**:
   - Open **"Live readings"**. Show how CNC Mills display vibration/RPM while AGVs display battery/heading.
4. **Demonstrate Query 1 ("Unusual Events Today")**:
   - Open **"Unusual today"**. Point out `DEV-CNC-004` (vibration harmonic spike) and `DEV-PDU-002` (voltage surge). Explain how `$setWindowFields` computed the rolling standard deviation and flagged $Z \ge 2.5$.
5. **Demonstrate Query 2 ("Failure Prediction")**:
   - Open **"Failure risk"**. Show machine risk scores. `DEV-CNC-004` is ranked #1 with `CRITICAL_FAILURE_IMMINENT` due to climbing vibration (+9.8 mm/s delta) combined with thermal runaway (+36.4°C).
6. **Live Fault Injection**:
   - Open **"Fault lab"**. Click **"Start ramp"** on `DEV-CNC-001`.
   - Click **"Start live readings"** in the top bar.
   - Switch back to Query 2; demonstrate the risk score of `DEV-CNC-001` progressively climbing in real time!
7. **Explain Index Optimization**:
   - Open **"Index performance"**. Walk through the measured results and explain honestly where the index helped (documents examined, `$near`, error filter) and where it did not at this data size.
