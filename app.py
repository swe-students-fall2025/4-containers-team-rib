from datetime import datetime, timedelta
import os
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "posture")
SLOUCH_THRESHOLD = float(os.getenv("SLOUCH_THRESHOLD", "0.6"))


client = MongoClient(MONGO_URL)
db = client[MONGO_DB]


app = Flask(__name__)
app.config["KEY_NAME"] = os.getenv("KEY_NAME", "change-me")


# --- Helpers ---
def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"

# Expected document shapes (ingested by ML client):
# samples: { ts: datetime, slouch_prob: float (0..1), label: "good"|"slouch" }
# events: { ts: datetime, type: "enter_slouch"|"exit_slouch", prob: float }

# Indexes (created once at startup)
db["samples"].create_index([("ts", DESCENDING)])
db["events"].create_index([("ts", DESCENDING)])

# --- Web pages ---
@app.get("/")
def index():
    return render_template("index.html", slouch_threshold=SLOUCH_THRESHOLD)

# --- APIs for UI ---
@app.get("/api/latest")
def api_latest():
    doc = db.samples.find_one(sort=[("ts", DESCENDING)])
    if not doc:
        return jsonify({"ok": True, "latest": None})
    latest = {
        "ts": _iso(doc["ts"]),
        "slouch_prob": float(doc.get("slouch_prob", 0)),
        "label": doc.get("label", "unknown"),
        "is_slouch": float(doc.get("slouch_prob", 0)) >= SLOUCH_THRESHOLD,
    }
    return jsonify({"ok": True, "latest": latest, "threshold": SLOUCH_THRESHOLD})

@app.get("/api/metrics")
def api_metrics():
    """Return time-series samples since ?minutes= (default 30)."""
    try:
        minutes = int(request.args.get("minutes", 30))
    except ValueError:
        minutes = 30
        since = datetime.utcnow() - timedelta(minutes=minutes)

    cur = db.samples.find({"ts": {"$gte": since}}).sort("ts", ASCENDING)
    series = [
    {"ts": _iso(d["ts"]), "slouch_prob": float(d.get("slouch_prob", 0))}
    for d in cur
    ]
    return jsonify({"ok": True, "series": series, "since": _iso(since)})

@app.get("/api/events")
def api_events():
    limit = min(int(request.args.get("limit", 25)), 200)
    cur = db.events.find().sort("ts", DESCENDING).limit(limit)
    events = [
        {"ts": _iso(d["ts"]), "type": d.get("type"), "prob": float(d.get("prob", 0))}
        for d in cur
    ]
    return jsonify({"ok": True, "events": events})

@app.post("/api/dev/ingest-sample")
def ingest_sample():
    payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ts = datetime.utcnow()
    p = float(payload.get("slouch_prob", 0.0))
    label = "slouch" if p >= SLOUCH_THRESHOLD else "good"
    db.samples.insert_one({"ts": ts, "slouch_prob": p, "label": label})
    return jsonify({"ok": True})

@app.post("/api/dev/ingest-event")
def ingest_event():
    payload = request.get_json(force=True, silent=True) or {}
    ts = datetime.utcnow()
    db.events.insert_one({"ts": ts, "type": payload.get("type", "event"), "prob": float(payload.get("prob", 0))})
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)