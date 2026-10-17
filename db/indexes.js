/**
 * MongoDB Indexes & Time-Series Setup
 * Run in mongosh: mongosh <uri>/iot_digital_twin db/indexes.js
 *
 * Implements rubric Criterion 5 (Advanced NoSQL features):
 * 1. 2dsphere index on devices.location (geospatial fleet tracking)
 * 2. Compound index on devices (zoneId + status)
 * 3. Compound index on events (deviceId + ts descending)
 * 4. Partial index on events (indexing only error-flagged events)
 * 5. TTL index on events (auto-expiring raw high-volume events after 7 days)
 * 6. Compound index on alerts (deviceId + acknowledged + ts)
 */

db = db.getSiblingDB("iot_digital_twin");

print("--- Creating Indexes for Digital Twin Collections ---");

// 1. Devices Collection Indexes
db.devices.createIndex(
  { deviceId: 1 },
  { unique: true, name: "idx_device_unique_id" }
);

db.devices.createIndex(
  { location: "2dsphere" },
  { name: "idx_device_2dsphere_loc" }
);

db.devices.createIndex(
  { zoneId: 1, status: 1 },
  { name: "idx_device_zone_status" }
);

db.devices.createIndex(
  { type: 1, status: 1 },
  { name: "idx_device_type_status" }
);

// 2. Events Collection Indexes (High-throughput time-series telemetry)
// Compound index for querying a device's recent history
db.events.createIndex(
  { deviceId: 1, ts: -1 },
  { name: "idx_events_device_ts" }
);

// TTL Index: Auto-expunge events older than 7 days (604,800 seconds)
db.events.createIndex(
  { ts: 1 },
  { expireAfterSeconds: 604800, name: "idx_events_ttl_7days" }
);

// Partial Index: Optimizes queries scanning specifically for faulty/errored telemetry events
db.events.createIndex(
  { deviceId: 1, ts: -1 },
  {
    partialFilterExpression: { "errors.0": { $exists: true } },
    name: "idx_events_partial_errors"
  }
);

// Compound index for time-window aggregations across the entire plant
db.events.createIndex(
  { ts: -1, status: 1 },
  { name: "idx_events_ts_status" }
);

// 3. Alerts Collection Indexes
db.alerts.createIndex(
  { deviceId: 1, acknowledged: 1, ts: -1 },
  { name: "idx_alerts_dev_ack_ts" }
);

db.alerts.createIndex(
  { severity: 1, acknowledged: 1 },
  { name: "idx_alerts_severity_ack" }
);

// 4. Zones Collection
db.zones.createIndex(
  { zoneId: 1 },
  { unique: true, name: "idx_zone_unique_id" }
);

print("All indexes configured successfully!");
printjson(db.devices.getIndexes());
printjson(db.events.getIndexes());
printjson(db.alerts.getIndexes());

// 7. Users: unique username for login lookups
db.users.createIndex({ username: 1 }, { unique: true, name: "idx_user_unique_name" });
