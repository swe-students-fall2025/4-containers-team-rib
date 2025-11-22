"""ML client that writes posture samples and events to MongoDB"""
# pylint: disable=no-member

import os
import time
from datetime import datetime, timezone

import cv2
import numpy as np
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi

MODEL_PATH = os.path.join(os.path.dirname(__file__), "my-pose-model")


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


def load_model():
    """Load the posture estimation model."""
    print("tensorflowjs import and related code removed.")


def get_webcam_frame():
    """Capture a frame from the webcam."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None

    frame = cv2.resize(frame, (257, 257))
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = frame.astype(np.float32) / 255.0
    frame = np.expand_dims(frame, axis=0)
    return frame


def predict_posture(model, frame):
    """Predict the posture based on the frame."""
    try:
        predictions = model.predict(frame)
        slouch_prob = predictions[0][0]
        return float(slouch_prob)
    except (AttributeError, IndexError, ValueError) as e:
        print(f"Error during prediction: {e}")
        return None


def log_event(event_type: str, prob: float):
    """Log an event to the database."""
    event = {
        "ts": datetime.now(timezone.utc),
        "type": event_type,
        "prob": float(prob),
    }
    db.events.insert_one(event)
    return event


def _latest_label():
    """Get the latest label from the samples."""
    doc = db.samples.find_one(sort=[("ts", DESCENDING)])
    return doc.get("label") if doc else None


def ingest_dummy_sample(prob=0.5):
    """Ingest a dummy sample for testing."""
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


def ingest_live_sample(model):
    """Ingest a live sample from the webcam."""
    frame = get_webcam_frame()
    if frame is None:
        print("Failed to capture webcam frame")
        return None

    slouch_prob = predict_posture(model, frame)
    if slouch_prob is None:
        print("Failed to get prediction")
        return None

    previous_label = _latest_label()
    doc = {
        "ts": datetime.now(timezone.utc),
        "slouch_prob": float(slouch_prob),
        "label": "slouch" if slouch_prob >= threshold else "good",
    }
    db.samples.insert_one(doc)

    if previous_label != doc["label"]:
        event_type = "enter_slouch" if doc["label"] == "slouch" else "exit_slouch"
        log_event(event_type, doc["slouch_prob"])

    return doc


def run_monitoring_loop(interval=5):
    """Run the posture monitoring loop."""
    load_model()
    model = None
    if model is None:
        print("Failed to load model. Exiting.")
        return

    print(f"Starting posture monitoring (interval: {interval}s)")
    print(f"Slouch threshold: {threshold}")
    print("Press Ctrl+C to stop")

    try:
        while True:
            result = ingest_live_sample(model)
            if result:
                print(
                    f"{result['ts']}: {result['label']} (prob: {result['slouch_prob']:.2f})"
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped monitoring")


def test_camera():
    """Test the camera access."""
    print("Testing camera access...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Camera not opening")
        return False

    ret, _ = cap.read()
    cap.release()

    return bool(ret)


if __name__ == "__main__":
    import sys

    if "--test-camera" in sys.argv:
        test_camera()
    elif "--live" in sys.argv:
        if not test_camera():
            print("\nCan't start monitoring without working camera.")
            sys.exit(1)
        run_monitoring_loop()
    else:
        print(ingest_dummy_sample())
