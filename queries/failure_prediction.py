"""Query 2: 'Which machines show signs of failure?'

Rubric mapping:
- Multi-stage Aggregation Pipeline ($match, $sort, $group, $lookup, $project, $addFields)
- Multi-metric trend analysis: correlates rising vibration and temperature over time
- Aggregates hardware fault frequencies
- Computes composite Failure Risk Score (0 to 100) and operational risk category
- Ranks devices by failure urgency
"""

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.connection import get_db


def build_failure_prediction_pipeline(hours: int = 12):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    pipeline = [
        # Stage 1: Filter events within recent trend window
        {
            "$match": {
                "ts": {"$gte": cutoff}
            }
        },
        # Stage 2: Sort chronologically for accurate first/last baseline comparison
        {
            "$sort": {"deviceId": 1, "ts": 1}
        },
        # Stage 3: Group per machine and compute statistical trend metrics
        {
            "$group": {
                "_id": "$deviceId",
                "sampleCount": {"$sum": 1},
                "earliestTs": {"$first": "$ts"},
                "latestTs": {"$last": "$ts"},
                # Vibration trend
                "firstVibe": {"$first": "$readings.vibration_mms"},
                "lastVibe": {"$last": "$readings.vibration_mms"},
                "maxVibe": {"$max": "$readings.vibration_mms"},
                "avgVibe": {"$avg": "$readings.vibration_mms"},
                # Thermal trend
                "firstTemp": {"$first": "$readings.temperature_c"},
                "lastTemp": {"$last": "$readings.temperature_c"},
                "maxTemp": {"$max": "$readings.temperature_c"},
                "avgTemp": {"$avg": "$readings.temperature_c"},
                # Battery trend (for AGVs)
                "lastBattery": {"$last": "$readings.battery_pct"},
                # Error count
                "errorCount": {
                    "$sum": {
                        "$cond": [
                            {"$gt": [{"$size": {"$ifNull": ["$errors", []]}}, 0]},
                            1,
                            0,
                        ]
                    }
                },
                "errorSamples": {
                    "$addToSet": "$errors"
                },
            }
        },
        # Stage 4: Compute rate of rise (deltas)
        {
            "$project": {
                "deviceId": "$_id",
                "sampleCount": 1,
                "earliestTs": 1,
                "latestTs": 1,
                "maxVibe": {"$ifNull": ["$maxVibe", 0.0]},
                "lastVibe": {"$ifNull": ["$lastVibe", 0.0]},
                "vibeDelta": {
                    "$subtract": [
                        {"$ifNull": ["$maxVibe", 0.0]},
                        {"$ifNull": ["$firstVibe", 0.0]},
                    ]
                },
                "maxTemp": {"$ifNull": ["$maxTemp", 0.0]},
                "lastTemp": {"$ifNull": ["$lastTemp", 0.0]},
                "tempDelta": {
                    "$subtract": [
                        {"$ifNull": ["$maxTemp", 0.0]},
                        {"$ifNull": ["$firstTemp", 0.0]},
                    ]
                },
                "lastBattery": 1,
                "errorCount": 1,
                "errorSamples": {
                    "$reduce": {
                        "input": "$errorSamples",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]},
                    }
                },
            }
        },
        # Stage 5: Composite Failure Risk Scoring Algorithm (0 to 100)
        {
            "$addFields": {
                # Vibration score component (max 40 pts)
                "vibeRiskComponent": {
                    "$cond": [
                        {"$gte": ["$maxVibe", 10.0]},
                        40.0,
                        {"$cond": [
                            {"$gte": ["$maxVibe", 5.0]},
                            25.0,
                            {"$cond": [{"$gt": ["$vibeDelta", 2.0]}, 15.0, 0.0]}
                        ]}
                    ]
                },
                # Temperature score component (max 30 pts)
                "tempRiskComponent": {
                    "$cond": [
                        {"$gte": ["$maxTemp", 90.0]},
                        30.0,
                        {"$cond": [
                            {"$gte": ["$maxTemp", 75.0]},
                            20.0,
                            {"$cond": [{"$gt": ["$tempDelta", 15.0]}, 15.0, 0.0]}
                        ]}
                    ]
                },
                # Hardware Error component (max 20 pts)
                "errorRiskComponent": {
                    "$cond": [
                        {"$gt": ["$errorCount", 5]},
                        20.0,
                        {"$cond": [{"$gt": ["$errorCount", 0]}, 10.0, 0.0]}
                    ]
                },
                # Battery Critical component (max 15 pts)
                "batteryRiskComponent": {
                    "$cond": [
                        {"$and": [{"$ne": ["$lastBattery", None]}, {"$lt": ["$lastBattery", 10.0]}]},
                        15.0,
                        0.0
                    ]
                },
            }
        },
        # Stage 6: Calculate total risk score and diagnostic flags
        {
            "$addFields": {
                "rawRiskScore": {
                    "$add": [
                        "$vibeRiskComponent",
                        "$tempRiskComponent",
                        "$errorRiskComponent",
                        "$batteryRiskComponent",
                    ]
                }
            }
        },
        {
            "$addFields": {
                "failureRiskScore": {
                    "$min": [100.0, "$rawRiskScore"]
                },
                "riskCategory": {
                    "$cond": [
                        {"$gte": ["$rawRiskScore", 75.0]},
                        "CRITICAL_FAILURE_IMMINENT",
                        {"$cond": [
                            {"$gte": ["$rawRiskScore", 45.0]},
                            "HIGH_MAINTENANCE_REQUIRED",
                            {"$cond": [
                                {"$gte": ["$rawRiskScore", 20.0]},
                                "ELEVATED_ATTENTION",
                                "NORMAL_HEALTHY"
                            ]}
                        ]}
                    ]
                },
            }
        },
        # Stage 7: Join with devices collection for plant twin context
        {
            "$lookup": {
                "from": "devices",
                "localField": "deviceId",
                "foreignField": "deviceId",
                "as": "device",
            }
        },
        {
            "$unwind": {
                "path": "$device",
                "preserveNullAndEmptyArrays": True,
            }
        },
        # Stage 8: Join zone data
        {
            "$lookup": {
                "from": "zones",
                "localField": "device.zoneId",
                "foreignField": "zoneId",
                "as": "zone",
            }
        },
        {
            "$unwind": {
                "path": "$zone",
                "preserveNullAndEmptyArrays": True,
            }
        },
        # Stage 9: Final presentation projection
        {
            "$project": {
                "_id": 0,
                "deviceId": 1,
                "deviceName": "$device.name",
                "deviceType": "$device.type",
                "zoneId": "$device.zoneId",
                "zoneName": "$zone.name",
                "location": "$device.location",
                "failureRiskScore": {"$round": ["$failureRiskScore", 1]},
                "riskCategory": 1,
                "lastVibe": {"$round": ["$lastVibe", 2]},
                "maxVibe": {"$round": ["$maxVibe", 2]},
                "vibeDelta": {"$round": ["$vibeDelta", 2]},
                "lastTemp": {"$round": ["$lastTemp", 1]},
                "maxTemp": {"$round": ["$maxTemp", 1]},
                "tempDelta": {"$round": ["$tempDelta", 1]},
                "lastBattery": "$lastBattery",
                "errorCount": "$errorCount",
                "activeFaultCodes": "$errorSamples",
                "sampleCount": 1,
            }
        },
        # Stage 10: Sort by failure risk descending
        {
            "$sort": {"failureRiskScore": -1}
        },
    ]

    return pipeline


def run_failure_prediction_query(hours: int = 12):
    """Executes the failure prediction aggregation and returns machine risk ranking."""
    db = get_db()
    pipeline = build_failure_prediction_pipeline(hours=hours)
    results = list(db.events.aggregate(pipeline))
    return results


if __name__ == "__main__":
    ranked_machines = run_failure_prediction_query(hours=12)
    print(f"\n--- Machine Failure Risk Ranking (Analyzed {len(ranked_machines)} Devices) ---")
    for m in ranked_machines[:6]:
        print(f"[{m['riskCategory']}] Score: {m['failureRiskScore']}/100 | {m['deviceId']} ({m.get('deviceName')})")
        print(f"   Zone: {m.get('zoneName')} | Type: {m.get('deviceType')}")
        print(f"   Vibration: max {m['maxVibe']} mm/s (delta +{m['vibeDelta']}) | Temp: max {m['maxTemp']} C (delta +{m['tempDelta']})")
        print(f"   Errors: {m['errorCount']} occurrences | Fault Codes: {m['activeFaultCodes']}\n")
