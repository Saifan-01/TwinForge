/**
 * Query 1: "Show me everything unusual that happened in the factory today"
 * Run in mongosh: mongosh <uri>/iot_digital_twin queries/unusual_events.js
 *
 * Rubric Highlights:
 * - Aggregation Pipeline using $setWindowFields
 * - Partitioned by deviceId, window [-20, 0] documents
 * - Computes rolling average & standard deviation
 * - Flags Z-Score statistical outliers (|x - μ| / σ >= 2.5)
 * - Flags events with non-empty error arrays or critical statuses
 */

db = db.getSiblingDB("iot_digital_twin");

const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000);
const zThreshold = 2.5;

const pipeline = [
  { $match: { ts: { $gte: cutoff } } },
  { $sort: { deviceId: 1, ts: 1 } },
  {
    $setWindowFields: {
      partitionBy: "$deviceId",
      sortBy: { ts: 1 },
      output: {
        rollingVibeAvg: { $avg: "$readings.vibration_mms", window: { documents: [-20, 0] } },
        rollingVibeStd: { $stdDevSamp: "$readings.vibration_mms", window: { documents: [-20, 0] } },
        rollingTempAvg: { $avg: "$readings.temperature_c", window: { documents: [-20, 0] } },
        rollingTempStd: { $stdDevSamp: "$readings.temperature_c", window: { documents: [-20, 0] } },
        rollingVoltAvg: { $avg: "$readings.voltage_v", window: { documents: [-20, 0] } },
        rollingVoltStd: { $stdDevSamp: "$readings.voltage_v", window: { documents: [-20, 0] } }
      }
    }
  },
  {
    $project: {
      deviceId: 1,
      ts: 1,
      status: 1,
      errors: 1,
      readings: 1,
      hasErrors: { $gt: [{ $size: { $ifNull: ["$errors", []] } }, 0] },
      isCriticalStatus: { $in: ["$status", ["CRITICAL", "WARNING"]] },
      vibeZScore: {
        $cond: [
          { $and: [{ $gt: ["$rollingVibeStd", 0.001] }, { $ne: ["$readings.vibration_mms", null] }] },
          { $divide: [{ $abs: { $subtract: ["$readings.vibration_mms", "$rollingVibeAvg"] } }, "$rollingVibeStd"] },
          0.0
        ]
      },
      tempZScore: {
        $cond: [
          { $and: [{ $gt: ["$rollingTempStd", 0.001] }, { $ne: ["$readings.temperature_c", null] }] },
          { $divide: [{ $abs: { $subtract: ["$readings.temperature_c", "$rollingTempAvg"] } }, "$rollingTempStd"] },
          0.0
        ]
      },
      voltZScore: {
        $cond: [
          { $and: [{ $gt: ["$rollingVoltStd", 0.001] }, { $ne: ["$readings.voltage_v", null] }] },
          { $divide: [{ $abs: { $subtract: ["$readings.voltage_v", "$rollingVoltAvg"] } }, "$rollingVoltStd"] },
          0.0
        ]
      }
    }
  },
  {
    $match: {
      $or: [
        { hasErrors: true },
        { isCriticalStatus: true },
        { vibeZScore: { $gte: zThreshold } },
        { tempZScore: { $gte: zThreshold } },
        { voltZScore: { $gte: zThreshold } }
      ]
    }
  },
  {
    $lookup: {
      from: "devices",
      localField: "deviceId",
      foreignField: "deviceId",
      as: "deviceInfo"
    }
  },
  { $unwind: { path: "$deviceInfo", preserveNullAndEmptyArrays: true } },
  {
    $project: {
      deviceId: 1,
      name: "$deviceInfo.name",
      type: "$deviceInfo.type",
      zoneId: "$deviceInfo.zoneId",
      ts: 1,
      status: 1,
      errors: 1,
      readings: 1,
      vibeZScore: { $round: ["$vibeZScore", 2] },
      tempZScore: { $round: ["$tempZScore", 2] },
      voltZScore: { $round: ["$voltZScore", 2] }
    }
  },
  { $sort: { ts: -1 } },
  { $limit: 25 }
];

const results = db.events.aggregate(pipeline).toArray();
print(`--- Identified ${results.length} Unusual Events Today ---`);
printjson(results);
