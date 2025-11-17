![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)

# Containerized App Exercise

Build a containerized app that uses machine learning. See [instructions](./instructions.md) for details.

### Web App (Flask)
Run the dashboard that visualizes posture status and time-series metrics.

#### Local (requires `mongodb` running)
export FLASK_ENV=development
export MONGO_URL="mongodb://localhost:27017"
export MONGO_DB=posture
python web-app/app.py

Open http://localhost:5000

#### Docker
cd web-app
docker build -t posture-web:latest .
docker run --rm -p 5000:5000 --env-file .env posture-web:latest

#### Endpoints
GET / – Dashboard
GET /api/latest – Latest sample { ts, slouch_prob, label, is_slouch }
GET /api/metrics – Time series for last ?minutes=30
GET /api/events – Recent slouch enter/exit events
POST /api/dev/ingest-sample – Dev-only ingestion { slouch_prob }
POST /api/dev/ingest-event – Dev-only event { type, prob }

The ML client should write to:
- samples(ts: datetime, slouch_prob: float, label: "good"|"slouch")
- events(ts: datetime, type: string, prob: float)
