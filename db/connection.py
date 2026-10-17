import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "iot_digital_twin")

_client = None


def get_mongo_client(uri: str = None) -> MongoClient:
    """Returns a singleton MongoClient instance."""
    global _client
    target_uri = uri or MONGO_URI
    if _client is None:
        _client = MongoClient(target_uri, serverSelectionTimeoutMS=4000)
    return _client


def get_db(db_name: str = None):
    """Returns the MongoDB database instance."""
    client = get_mongo_client()
    return client[db_name or DB_NAME]


def check_connection() -> dict:
    """Verifies MongoDB connectivity via an admin ping command."""
    try:
        client = get_mongo_client()
        res = client.admin.command("ping")
        return {"status": "connected", "ping": res.get("ok", 0) == 1.0, "uri": MONGO_URI, "db": DB_NAME}
    except Exception as e:
        return {"status": "error", "error": str(e), "uri": MONGO_URI, "db": DB_NAME}
