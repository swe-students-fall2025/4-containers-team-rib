"""Unit tests for the ML client helpers."""
# pylint: disable=missing-function-docstring,too-few-public-methods,invalid-name,unnecessary-lambda,unused-argument,mixed-line-endings

import types
from datetime import datetime, timezone

import numpy as np
import pytest
from pymongo import DESCENDING

from machine_learning_client import client


class _FakeCollection:
    """Minimal in-memory collection stub."""

    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        return doc

    def find_one(self, sort=None):
        if not self.docs:
            return None
        if sort:
            key, order = sort[0]
            reverse = order == DESCENDING
            return sorted(self.docs, key=lambda d: d[key], reverse=reverse)[0]
        return self.docs[0]


class _FakeDB:
    """In-memory DB stub."""

    def __init__(self):
        self.samples = _FakeCollection()
        self.events = _FakeCollection()


def test_log_event_writes_event(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(client, "db", fake_db)
    evt = client.log_event("enter_slouch", 0.9)
    assert evt["type"] == "enter_slouch"
    assert fake_db.events.docs[0]["prob"] == pytest.approx(0.9)


def test_ingest_dummy_sample_creates_event_on_label_change(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "threshold", 0.6)

    doc = client.ingest_dummy_sample(prob=0.8)
    assert doc["label"] == "slouch"
    assert len(fake_db.samples.docs) == 1
    assert len(fake_db.events.docs) == 1
    assert fake_db.events.docs[0]["type"] == "enter_slouch"


def test_ingest_dummy_sample_no_event_when_same_label(monkeypatch):
    fake_db = _FakeDB()
    # seed previous slouch sample
    fake_db.samples.insert_one({"ts": datetime.now(timezone.utc), "label": "slouch"})

    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "threshold", 0.6)

    doc = client.ingest_dummy_sample(prob=0.8)
    assert doc["label"] == "slouch"
    assert len(fake_db.events.docs) == 0


def test_ingest_live_sample_handles_missing_frame(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "get_webcam_frame", lambda: None)
    result = client.ingest_live_sample(model=types.SimpleNamespace())
    assert result is None
    assert len(fake_db.samples.docs) == 0
    assert len(fake_db.events.docs) == 0


def test_predict_posture_invalid_model_returns_none():
    bad_model = types.SimpleNamespace()  # no predict method
    assert client.predict_posture(bad_model, frame=None) is None


def test_predict_posture_success():
    class _Model:
        def predict(self, frame):
            return [[0.3]]

    assert client.predict_posture(_Model(), frame=np.zeros((1, 1))) == pytest.approx(0.3)


def test_ingest_live_sample_records_exit_event(monkeypatch):
    fake_db = _FakeDB()
    # start in slouch state
    fake_db.samples.insert_one({"ts": datetime.now(timezone.utc), "label": "slouch"})

    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "threshold", 0.6)
    monkeypatch.setattr(client, "get_webcam_frame", lambda: object())

    def _predict_exit(_model, _frame):
        return 0.2

    monkeypatch.setattr(client, "predict_posture", _predict_exit)

    doc = client.ingest_live_sample(model=types.SimpleNamespace(predict=lambda f: [[0.2]]))
    assert doc is not None
    assert doc["label"] == "good"
    assert len(fake_db.events.docs) == 1
    assert fake_db.events.docs[0]["type"] == "exit_slouch"


def test_ingest_live_sample_records_enter_event(monkeypatch):
    fake_db = _FakeDB()
    fake_db.samples.insert_one({"ts": datetime.now(timezone.utc), "label": "good"})

    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "threshold", 0.6)
    monkeypatch.setattr(client, "get_webcam_frame", lambda: object())

    def _predict_enter(_model, _frame):
        return 0.9

    monkeypatch.setattr(client, "predict_posture", _predict_enter)

    doc = client.ingest_live_sample(model=types.SimpleNamespace(predict=lambda f: [[0.9]]))
    assert doc["label"] == "slouch"
    assert len(fake_db.events.docs) == 1
    assert fake_db.events.docs[0]["type"] == "enter_slouch"


def test_get_webcam_frame_handles_closed_camera(monkeypatch):
    class _Cap:
        def isOpened(self):
            return False

    monkeypatch.setattr(client.cv2, "VideoCapture", lambda *_: _Cap())
    assert client.get_webcam_frame() is None


def test_get_webcam_frame_returns_frame(monkeypatch):
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)

    class _Cap:
        def __init__(self):
            self.released = False

        def isOpened(self):
            return True

        def read(self):
            return True, dummy

        def release(self):
            self.released = True

    monkeypatch.setattr(client.cv2, "VideoCapture", lambda *_: _Cap())
    frame = client.get_webcam_frame()
    assert frame is not None
    assert frame.shape == (1, 257, 257, 3)
    assert frame.min() >= 0 and frame.max() <= 1


def test_run_monitoring_loop_exits_when_model_missing(monkeypatch, capsys):
    monkeypatch.setattr(client, "load_model", lambda: None)
    # Avoid actual loop by using default None model early exit
    client.run_monitoring_loop(interval=0)
    captured = capsys.readouterr()
    assert "Failed to load model" in captured.out


def test_ingest_live_sample_skips_when_prediction_none(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(client, "db", fake_db)
    monkeypatch.setattr(client, "threshold", 0.6)
    monkeypatch.setattr(client, "get_webcam_frame", lambda: object())
    monkeypatch.setattr(client, "predict_posture", lambda model, frame: None)

    doc = client.ingest_live_sample(model=types.SimpleNamespace())
    assert doc is None
    assert len(fake_db.samples.docs) == 0
    assert len(fake_db.events.docs) == 0


def test_get_webcam_frame_handles_read_failure(monkeypatch):
    class _Cap:
        def isOpened(self):
            return True

        def read(self):
            return False, None

        def release(self):
            pass

    monkeypatch.setattr(client.cv2, "VideoCapture", lambda *_: _Cap())
    assert client.get_webcam_frame() is None


def test_predict_posture_handles_index_error():
    class _BadModel:
        def predict(self, frame):
            return [[]]

    assert client.predict_posture(_BadModel(), frame=np.zeros((1, 1))) is None


def test_test_camera_success(monkeypatch):
    class _Cap:
        def isOpened(self):
            return True

        def read(self):
            return True, None

        def release(self):
            pass

    monkeypatch.setattr(client.cv2, "VideoCapture", lambda *_: _Cap())
    assert client.test_camera() is True


def test_test_camera_failure(monkeypatch):
    class _Cap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(client.cv2, "VideoCapture", lambda *_: _Cap())
    assert client.test_camera() is False
