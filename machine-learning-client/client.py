"""ML client that writes posture samples and events to MongoDB"""

import os
import json
import time
import cv2
import numpy as np
import tensorflow as tf
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi


def _get_db():
    mongo_url = os.getenv("MONGO_URL")
    db_name = os.getenv("MONGO_DB", "posture")

    if mongo_url:client = MongoClient(mongo_url)
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

# Load model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "my-pose-model")


def load_model():
    try:
        try:
            import tensorflowjs as tfjs
            model = tfjs.converters.load_keras_model(MODEL_PATH)
            print(f"Model loaded successfully from {MODEL_PATH}")
            return model
        except ImportError:
            print("tensorflowjs not installed. Install with: pip install tensorflowjs")
            print("Then convert the model with: tensorflowjs_converter --input_format=tfjs_layers_model --output_format=keras_saved_model my-pose-model/ converted_model/")
            return None
    except Exception as e:
        print(f"Error loading model: {e}")
        return None


def get_webcam_frame():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        print("Possible issues:")
        print("  - Camera is being used by another application")
        print("  - Camera permissions not granted")
        print("  - No camera detected")
        return None
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Error: Could not read frame from webcam")
        return None
    
    frame = cv2.resize(frame, (257, 257))
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = frame.astype(np.float32) / 255.0
    frame = np.expand_dims(frame, axis=0)
    return frame


def predict_posture(model, frame):
    try:
        predictions = model.predict(frame)
        slouch_prob = predictions[0][0]
        return float(slouch_prob)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return None



def log_event(event_type: str, prob: float):
    event = {
        "ts": datetime.now(timezone.utc),
        "type": event_type,
        "prob": float(prob),
    }
    db.events.insert_one(event)
    return event


def _latest_label():
    doc = db.samples.find_one(sort=[("ts", DESCENDING)])
    return doc.get("label") if doc else None


def ingest_dummy_sample(prob=0.5):
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
    model = load_model()
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
                print(f"{result['ts']}: {result['label']} (prob: {result['slouch_prob']:.2f})")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped monitoring")


def test_camera():
    print("Testing camera access...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Camera could not be opened")
        print("\nTroubleshooting:")
        print("  1. Check if another app is using the camera (Teams, Zoom, etc.)")
        print("  2. Verify camera permissions in Windows Settings")
        print("  3. Try restarting your computer")
        return False
    
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        print(f"✓ Camera working! Frame captured: {frame.shape}")
        return True
    else:
        print("❌ Camera opened but couldn't capture frame")
        return False


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