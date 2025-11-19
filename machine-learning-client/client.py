"""ML client that writes posture samples and events to MongoDB"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi


def _get_db():
    mongo_url = os.getenv("MONGO_URL")
    db_name = os.getenv("MONGO_DB", "posture")

    if mongo_url:
        client = MongoClient(mongo_url)
    else:
        user = os.getenv("MONGO_USERNAME")
        password = os.getenv("MONGO_PASSWORD")
        host = os.getenv("MONGO_HOST", "ribs.xo4actr.mongodb.net")
        app_name = os.getenv("APP_NAME", "RIBS")
        uri = f"mongodb+srv://{user}:{password}@{host}/?appName={app_name}"
        client = MongoClient(uri, server_api=ServerApi("1"))

    return client[db_name]


db = _get_db()
threshold = float(os.getenv("SLOUCH_THRESHOLD", "0.6"))


def log_event(event_type: str, prob: float):
    """Insert slouch transition event"""
    event = {
        "ts": datetime.now(timezone.utc),
        "type": event_type,
        "prob": float(prob),
    }
    db.events.insert_one(event)
    return event


def _latest_label():
    """Return most recent posture label"""
    doc = db.samples.find_one(sort=[("ts", DESCENDING)])
    return doc.get("label") if doc else None


def ingest_dummy_sample(prob=0.5):
    """Insert dummy sample and log transitions"""
    previous_label = _latest_label()
    doc = {
        "ts": datetime.now(timezone.utc),
        "slouch_prob": float(prob),
        "label": "slouch" if prob >= threshold else "good",
    }
    db.samples.insert_one(doc)
    if previous_label != doc["label"]:
        event_type = "enter_slouch" if doc["label"] == "slouch" else "exit_slouch"
        log_event(event_type, doc["slouch_prob"])
    return doc


if __name__ == "__main__":
    print(ingest_dummy_sample())
