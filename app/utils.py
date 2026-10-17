"""JSON serialization utilities for MongoDB documents."""

import json
from datetime import datetime, date
from bson import ObjectId


class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle BSON ObjectId, datetime, and date."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


def serialize_doc(doc):
    """Recursively serializes MongoDB document dictionaries into JSON-safe structures."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, (datetime, date)):
                result[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                result[k] = serialize_doc(v)
            else:
                result[k] = v
        return result
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, (datetime, date)):
        return doc.isoformat()
    return doc
