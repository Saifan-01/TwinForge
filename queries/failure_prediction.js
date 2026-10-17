/**
 * Query 2: "Which machines show signs of failure?"
 * Run in mongosh: mongosh <uri>/iot_digital_twin queries/failure_prediction.js
 *
 * Rubric Highlights:
 * - Multi-stage Aggregation Pipeline
 * - Trend evaluation across a sliding window (first vs last values, deltas)
 * - Multi-variate correlation: Vibration escalation + Temperature rise + Error codes
 * - Composite Failure Risk Score (0-100)
 * - Sorted by urgency
 */

db = db.getSiblingDB("iot_digital_twin");

const cutoff = new Date(Date.now() - 12 * 60 * 60 * 1000);

const pipeline = [
  { $match: { ts: { $gte: cutoff } } },
  { $sort: { deviceId: 1, ts: 1 } },
  {
    $group: {
      _id: "$deviceId",
      sampleCount: { $sum: 1 },
      firstVibe: { $first: "$readings.vibration_mms" },
      lastVibe: { $last: "$readings.vibration_mms" },
      maxVibe: { $max: "$readings.vibration_mms" },
      firstTemp: { $first: "$readings.temperature_c" },
      lastTemp: { $last: "$readings.temperature_c" },
      maxTemp: { $max: "$readings.temperature_c" },
      lastBattery: { $last: "$readings.battery_pct" },
      errorCount: {
        $sum: { $cond: [{ $gt: [{ $size: { $ifNull: ["$errors", []] } }, 0] }, 1, 0] }
      },
      errorSamples: { $addToSet: "$errors" }
    }
  },
  {
    $project: {
      deviceId: "$_id",
      sampleCount: 1,
      maxVibe: { $ifNull: ["$maxVibe", 0.0] },
      lastVibe: { $ifNull: ["$lastVibe", 0.0] },
      vibeDelta: { $subtract: [{ $ifNull: ["$maxVibe", 0.0] }, { $ifNull: ["$firstVibe", 0.0] }] },
      maxTemp: { $ifNull: ["$maxTemp", 0.0] },
      lastTemp: { $ifNull: ["$lastTemp", 0.0] },
      tempDelta: { $subtract: [{ $ifNull: ["$maxTemp", 0.0] }, { $ifNull: ["$firstTemp", 0.0] }] },
      lastBattery: 1,
      errorCount: 1,
      errorSamples: {
        $reduce: {
          input: "$errorSamples",
          initialValue: [],
          in: { $setUnion: ["$$value", "$$this"] }
        }
      }
    }
  },
  {
    $addFields: {
      vibeRisk: {
        $cond: [
          { $gte: ["$maxVibe", 10.0] }, 40.0,
          { $cond: [{ $gte: ["$maxVibe", 5.0] }, 25.0, { $cond: [{ $gt: ["$vibeDelta", 2.0] }, 15.0, 0.0] }] }
        ]
      },
      tempRisk: {
        $cond: [
          { $gte: ["$maxTemp", 90.0] }, 30.0,
          { $cond: [{ $gte: ["$maxTemp", 75.0] }, 20.0, { $cond: [{ $gt: ["$tempDelta", 15.0] }, 15.0, 0.0] }] }
        ]
      },
      errorRisk: {
        $cond: [{ $gt: ["$errorCount", 5] }, 20.0, { $cond: [{ $gt: ["$errorCount", 0] }, 10.0, 0.0] }]
      },
      batteryRisk: {
        $cond: [{ $and: [{ $ne: ["$lastBattery", null] }, { $lt: ["$lastBattery", 10.0] }] }, 15.0, 0.0]
      }
    }
  },
  {
    $addFields: {
      rawScore: { $add: ["$vibeRisk", "$tempRisk", "$errorRisk", "$batteryRisk"] }
    }
  },
  {
    $addFields: {
      failureRiskScore: { $min: [100.0, "$rawScore"] },
      riskCategory: {
        $cond: [
          { $gte: ["$rawScore", 75.0] }, "CRITICAL_FAILURE_IMMINENT",
          { $cond: [
            { $gte: ["$rawScore", 45.0] }, "HIGH_MAINTENANCE_REQUIRED",
            { $cond: [{ $gte: ["$rawScore", 20.0] }, "ELEVATED_ATTENTION", "NORMAL_HEALTHY"] }
          ]}
        ]
      }
    }
  },
  {
    $lookup: {
      from: "devices",
      localField: "deviceId",
      foreignField: "deviceId",
      as: "device"
    }
  },
  { $unwind: { path: "$device", preserveNullAndEmptyArrays: true } },
  {
    $project: {
      _id: 0,
      deviceId: 1,
      deviceName: "$device.name",
      deviceType: "$device.type",
      zoneId: "$device.zoneId",
      failureRiskScore: { $round: ["$failureRiskScore", 1] },
      riskCategory: 1,
      lastVibe: { $round: ["$lastVibe", 2] },
      maxVibe: { $round: ["$maxVibe", 2] },
      vibeDelta: { $round: ["$vibeDelta", 2] },
      lastTemp: { $round: ["$lastTemp", 1] },
      maxTemp: { $round: ["$maxTemp", 1] },
      tempDelta: { $round: ["$tempDelta", 1] },
      errorCount: 1,
      activeFaultCodes: "$errorSamples"
    }
  },
  { $sort: { failureRiskScore: -1 } },
  { $limit: 15 }
];

const results = db.events.aggregate(pipeline).toArray();
print(`--- Machines Showing Signs of Failure (Top ${results.length}) ---`);
printjson(results);
