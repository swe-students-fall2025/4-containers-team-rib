"""Route tests for the Flask app."""
# pylint: disable=missing-function-docstring,redefined-outer-name
import json
from datetime import datetime, timedelta
import pytest

from app import app as flask_app, db

@pytest.fixture()
def app():
    yield flask_app
    db.samples.delete_many({})
    db.events.delete_many({})

@pytest.fixture()
def client(app):
    return app.test_client()

def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200

def test_latest_none(client):
    res = client.get("/api/latest")
    data = res.get_json()
    assert data["ok"] is True
    assert data["latest"] is None

def test_ingest_and_latest(client):
    # inject a sample
    payload = {"slouch_prob": 0.7}
    res = client.post(
        "/api/dev/ingest-sample",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert res.status_code == 200

    res2 = client.get("/api/latest")
    data = res2.get_json()
    assert data["ok"] is True
    assert data["latest"]["is_slouch"] is True

def test_metrics_series(client):
    now = datetime.utcnow()
    db.samples.insert_many([
        {"ts": now - timedelta(minutes=2), "slouch_prob": 0.2, "label": "good"},
        {"ts": now - timedelta(minutes=1), "slouch_prob": 0.8, "label": "slouch"},
    ])
    res = client.get("/api/metrics?minutes=5")
    data = res.get_json()
    assert data["ok"] is True
    assert len(data["series"]) >= 2
