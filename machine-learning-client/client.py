"""ML client that writes posture samples and events to MongoDB"""

import os
from datetime import datetime, timezone
from pymongo import DESCENDING
from db.db import db


def _get_db():
    return db


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
