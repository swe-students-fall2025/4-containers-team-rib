![Web App CI](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg?branch=main&label=web-app)
![ML Client CI](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg?branch=main&label=ml-client)

# Posture Tracker (Containers)

A three-container posture monitoring system:
- **Web app (Flask):** live dashboard with camera capture, posture status, charts, and event history.
- **ML client (Python):** runs the pose model, sends slouch/good posture samples and events to MongoDB.
- **MongoDB:** stores samples (`ts`, `slouch_prob`, `label`) and events (`ts`, `type`, `prob`).

## Team
- [Alif](https://github.com/Alif-4)
- [Alfardil](https://github.com/Alfardil)
- [TickyTacky](https://github.com/TickyTacky)
- [Sam](https://github.com/) <!-- replace with Sam's profile -->

## Repo Layout
- `app.py`, `templates/`, `static/` — Flask web UI and APIs.
- `machine-learning-client/` — ML client scripts (connects to Mongo, writes samples/events).
- `db/` — shared Mongo connection helper.
- `.github/workflows/lint.yml` — lint/format CI across subsystems.

## Prerequisites
- Python 3.10, Pipenv
- Docker (for MongoDB or container runs)
- MongoDB Atlas credentials **or** a local Mongo container

## Environment Variables
Create `.env` in the repo root (use `.env.example` as a template):
```
MONGO_USERNAME=common_user          # Atlas username (leave blank for local Mongo)
MONGO_PASSWORD=****                 # Atlas password
MONGO_DB=posture                    # database name
APP_NAME=RIBS                       # Atlas app name
MONGO_URL=mongodb://localhost:27017 # optional: overrides Atlas, use for local Mongo
SLOUCH_THRESHOLD=0.6                # cutoff for slouch vs good posture
```

## Database (MongoDB)
- **Local (Docker):**
  ```
  docker run --name mongodb -d -p 27017:27017 mongo
  ```
  Set `MONGO_URL=mongodb://localhost:27017` in `.env`.
- **Atlas:** use the team-provided `MONGO_USERNAME`, `MONGO_PASSWORD`, `APP_NAME`, `MONGO_DB`. Leave `MONGO_URL` unset.
- Collections are created on first write: `samples`, `events`.

## Web App (Flask)
### Local (all platforms)
1. Install deps:
   ```
   pipenv install
   ```
2. Run:
   ```
   pipenv run flask run
   ```
3. Open `http://127.0.0.1:5000`.

API overview:
- `GET /api/latest` — latest sample `{ts, slouch_prob, label, is_slouch}`
- `GET /api/metrics?minutes=30` — time series of samples
- `GET /api/events?limit=25` — recent events
- `POST /api/dev/ingest-sample` — dev-only ingestion `{slouch_prob}`
- `POST /api/dev/ingest-event` — dev-only `{type, prob}`

## Machine Learning Client
- Script: `machine-learning-client/client.py`
- Runs with the same `.env`:
  ```
  pipenv run python machine-learning-client/client.py
  ```
- Inserts posture samples and slouch enter/exit events into Mongo.

## Docker / Compose
- Mongo local: `docker run --name mongodb -d -p 27017:27017 mongo`
- Web app image:
  ```
  docker build -t posture-web:latest .
  docker run --rm -p 5000:5000 --env-file .env posture-web:latest
  ```
- Compose (when you add `docker-compose.yml`):
  - `web-app`: build from repo root, exposes `5000`, depends on `mongo`.
  - `ml-client`: runs `python machine-learning-client/client.py`, shares `.env`.
  - `mongo`: official `mongo` image, port `27017`.
  - Start everything: `docker-compose up --build`

## Testing, Linting, Formatting
- Lint: `pipenv run pylint **/*.py`
- Format check: `pipenv run black --check .`
- Tests (when added): `pipenv run pytest`
- CI mirrors these checks via `.github/workflows/lint.yml`.

## Starter Data
No starter dataset is required. To seed manually for UI testing:
```
pipenv run python -c "import requests; requests.post('http://127.0.0.1:5000/api/dev/ingest-sample', json={'slouch_prob':0.72})"
pipenv run python -c "import requests; requests.post('http://127.0.0.1:5000/api/dev/ingest-event', json={'type':'enter_slouch','prob':0.72})"
```

## Notes
- Keep secrets in `.env` (not committed). Share `.env.example` with dummy values.
- The lint workflow expects Python 3.10 and Pipenv; install deps before running locally.
