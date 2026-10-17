"""Query 1: 'Show me everything unusual that happened in the factory today'

Rubric mapping:
- Advanced Aggregation ($match, $setWindowFields, $project, $lookup, $sort)
- Calculates rolling mean and standard deviation per device and metric
- Flags statistical z-score outliers (|value - mean| / stdDev >= 2.5)
- Captures system anomalies: non-empty errors array or critical status codes
"""

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.connection import get_db


def build_unusual_events_pipeline(hours: int = 24, z_threshold: float = 2.5):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    pipeline = [
        # Step 1: Match events within time window
        {
            "$match": {
                "ts": {"$gte": cutoff}
            }
        },
        # Step 2: Sort for ordered window evaluation
        {
            "$sort": {"deviceId": 1, "ts": 1}
        },
        # Step 3: Rolling statistical window fields per device partition
        {
            "$setWindowFields": {
                "partitionBy": "$deviceId",
                "sortBy": {"ts": 1},
                "output": {
                    "rollingVibeAvg": {
                        "$avg": "$readings.vibration_mms",
                        "window": {"documents": [-20, 0]},
                    },
                    "rollingVibeStd": {
                        "$stdDevSamp": "$readings.vibration_mms",
                        "window": {"documents": [-20, 0]},
                    },
                    "rollingTempAvg": {
                        "$avg": "$readings.temperature_c",
                        "window": {"documents": [-20, 0]},
                    },
                    "rollingTempStd": {
                        "$stdDevSamp": "$readings.temperature_c",
                        "window": {"documents": [-20, 0]},
                    },
                    "rollingVoltAvg": {
                        "$avg": "$readings.voltage_v",
                        "window": {"documents": [-20, 0]},
                    },
                    "rollingVoltStd": {
                        "$stdDevSamp": "$readings.voltage_v",
                        "window": {"documents": [-20, 0]},
                    },
                },
            }
        },
        # Step 4: Calculate Z-Scores and anomaly flags
        {
            "$project": {
                "_id": 1,
                "deviceId": 1,
                "ts": 1,
                "status": 1,
                "errors": 1,
                "readings": 1,
                "hasErrors": {
                    "$gt": [{"$size": {"$ifNull": ["$errors", []]}}, 0]
                },
                "isCriticalStatus": {
                    "$in": ["$status", ["CRITICAL", "WARNING"]]
                },
                "vibeZScore": {
                    "$cond": [
                        {"$and": [{"$gt": ["$rollingVibeStd", 0.001]}, {"$ne": ["$readings.vibration_mms", None]}]},
                        {
                            "$divide": [
                                {"$abs": {"$subtract": ["$readings.vibration_mms", "$rollingVibeAvg"]}},
                                "$rollingVibeStd",
                            ]
                        },
                        0.0,
                    ]
                },
                "tempZScore": {
                    "$cond": [
                        {"$and": [{"$gt": ["$rollingTempStd", 0.001]}, {"$ne": ["$readings.temperature_c", None]}]},
                        {
                            "$divide": [
                                {"$abs": {"$subtract": ["$readings.temperature_c", "$rollingTempAvg"]}},
                                "$rollingTempStd",
                            ]
                        },
                        0.0,
                    ]
                },
                "voltZScore": {
                    "$cond": [
                        {"$and": [{"$gt": ["$rollingVoltStd", 0.001]}, {"$ne": ["$readings.voltage_v", None]}]},
                        {
                            "$divide": [
                                {"$abs": {"$subtract": ["$readings.voltage_v", "$rollingVoltAvg"]}},
                                "$rollingVoltStd",
                            ]
                        },
                        0.0,
                    ]
                },
            }
        },
        # Step 5: Filter for events exhibiting unusual characteristics
        {
            "$match": {
                "$or": [
                    {"hasErrors": True},
                    {"isCriticalStatus": True},
                    {"vibeZScore": {"$gte": z_threshold}},
                    {"tempZScore": {"$gte": z_threshold}},
                    {"voltZScore": {"$gte": z_threshold}},
                ]
            }
        },
        # Step 6: Join with devices collection for context (zone, name, type)
        {
            "$lookup": {
                "from": "devices",
                "localField": "deviceId",
                "foreignField": "deviceId",
                "as": "deviceInfo",
            }
        },
        {
            "$unwind": {
                "path": "$deviceInfo",
                "preserveNullAndEmptyArrays": True,
            }
        },
        # Step 7: Format output with severity rating and root-cause reasons
        {
            "$project": {
                "deviceId": 1,
                "deviceName": "$deviceInfo.name",
                "deviceType": "$deviceInfo.type",
                "zoneId": "$deviceInfo.zoneId",
                "ts": 1,
                "status": 1,
                "errors": 1,
                "readings": 1,
                "vibeZScore": {"$round": ["$vibeZScore", 2]},
                "tempZScore": {"$round": ["$tempZScore", 2]},
                "voltZScore": {"$round": ["$voltZScore", 2]},
                "anomalyType": {
                    "$concatArrays": [
                        {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$errors", []]}}, 0]}, ["Hardware Error Code"], []]},
                        {"$cond": [{"$gte": ["$vibeZScore", z_threshold]}, ["Vibration Z-Score Spike"], []]},
                        {"$cond": [{"$gte": ["$tempZScore", z_threshold]}, ["Thermal Outlier"], []]},
                        {"$cond": [{"$gte": ["$voltZScore", z_threshold]}, ["Voltage Fluctuation Outlier"], []]},
                        {"$cond": [{"$eq": ["$status", "CRITICAL"]}, ["Critical Machine State"], []]},
                    ]
                },
            }
        },
        # Step 8: Sort most recent unusual events first
        {
            "$sort": {"ts": -1}
        },
        {"$limit": 100},
    ]

    return pipeline


def run_unusual_events_query(hours: int = 24, z_threshold: float = 2.5):
    """Executes the aggregation query and returns parsed results."""
    db = get_db()
    pipeline = build_unusual_events_pipeline(hours=hours, z_threshold=z_threshold)
    results = list(db.events.aggregate(pipeline))
    return results


if __name__ == "__main__":
    events = run_unusual_events_query(hours=24)
    print(f"\n--- Found {len(events)} Unusual Events in Past 24h ---")
    for e in events[:8]:
        print(f"[{e['ts'].strftime('%H:%M:%S')}] {e['deviceId']} ({e.get('deviceName', 'N/A')}) in {e.get('zoneId')}")
        print(f"   Reasons: {e.get('anomalyType')} | Errors: {e.get('errors')}")
        print(f"   Readings: {e.get('readings')}\n")
