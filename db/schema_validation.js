/**
 * MongoDB Schema Validation via $jsonSchema
 * Run in mongosh: mongosh <uri>/iot_digital_twin db/schema_validation.js
 *
 * Implements governance without sacrificing NoSQL flexibility:
 * - Enforces required identifiers, device types, and GeoJSON structure
 * - Permits polymorphic capabilities and custom hardware specs
 */

db = db.getSiblingDB("iot_digital_twin");

// 1. Device Collection Validation
db.runCommand({
  collMod: "devices",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["deviceId", "name", "type", "zoneId", "status", "capabilities"],
      properties: {
        deviceId: {
          bsonType: "string",
          pattern: "^DEV-[A-Z0-9-]+$",
          description: "Must be a unique string starting with DEV-"
        },
        name: {
          bsonType: "string",
          description: "Human-readable label for device"
        },
        type: {
          enum: [
            "CNC_MILL",
            "AGV_FORKLIFT",
            "POWER_TRANSFORMER",
            "HVAC_CHILLER",
            "CLEANROOM_MONITOR",
            "VIBRATION_SENSOR"
          ],
          description: "Allowed industrial machine category"
        },
        zoneId: {
          bsonType: "string",
          description: "Plant zone or cell identifier"
        },
        status: {
          enum: ["ONLINE", "WARNING", "CRITICAL", "MAINTENANCE", "DECOMMISSIONED"],
          description: "Current operational lifecycle state"
        },
        capabilities: {
          bsonType: "array",
          minItems: 1,
          items: {
            bsonType: "string"
          },
          description: "Polymorphic telemetry channels supported by this hardware"
        },
        location: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: {
              enum: ["Point"],
              description: "Must be a GeoJSON Point"
            },
            coordinates: {
              bsonType: "array",
              minItems: 2,
              maxItems: 2,
              items: { bsonType: ["double", "int", "long"] },
              description: "[longitude, latitude] coordinates for 2dsphere indexing"
            }
          }
        },
        specs: {
          bsonType: "object",
          description: "Flexible per-device hardware specifications (NoSQL dynamic schema)"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

// 2. Alert Collection Validation
db.runCommand({
  collMod: "alerts",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["alertId", "deviceId", "severity", "message", "ts"],
      properties: {
        alertId: { bsonType: "string" },
        deviceId: { bsonType: "string" },
        severity: { enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
        message: { bsonType: "string" },
        acknowledged: { bsonType: "bool" },
        ts: { bsonType: "date" }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

// 3. User Collection Validation (login accounts)
db.runCommand({
  collMod: "users",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["username", "passwordHash", "role"],
      properties: {
        username: { bsonType: "string", minLength: 3 },
        passwordHash: { bsonType: "string" },
        role: { enum: ["admin", "viewer"] }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

print("Schema validation rules successfully applied to 'devices', 'alerts' and 'users' collections.");
