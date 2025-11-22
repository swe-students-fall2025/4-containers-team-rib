![Web App CI](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/web-app.yml/badge.svg?branch=main)
![ML Client CI](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/ml-client.yml/badge.svg?branch=main)

# Posture Tracker

A containerized posture tracking system that uses your webcam to estimate posture in real time. The ML client runs a pose model and streams posture samples to MongoDB. The Flask web app displays live status, a slouch probability gauge, and a 30-minute chart with percentages of time spent slouching vs good posture. 


- **Web app (Flask):** live dashboard with camera capture, posture status, charts, and event history.
- **ML client (Python):** runs the pose model, sends slouch/good posture samples and events to MongoDB.
- **MongoDB:** stores samples (`ts`, `slouch_prob`, `label`) and events (`ts`, `type`, `prob`).

## Team
- [Alif](https://github.com/Alif-4)
- [Alfardil]
- [TickyTacky]
- [Sam]

## Repo Layout
- `app.py`, `templates/`, `static/` : Flask web UI and APIs.
- `machine-learning-client/` : ML client scripts that connects to Mongo.
- `db/` : shared Mongo connection helper.

## System Requirements
- Python 3.10, Pipenv
- Docker
- MongoDB Atlas credentials or local Mongo container

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
- **Atlas:** use the team `MONGO_USERNAME`, `MONGO_PASSWORD`, `APP_NAME`, `MONGO_DB`. Leave `MONGO_URL` unset.
- Collections are created on first write: `samples`, `events`.

## Web App (Flask)
### Local
1. Install deps:
   ```
   pipenv install
   ```
3. Open Shell:
   ```
   pipenv shell
   ```
3. Run:
   ```
   flask run
   ```
4. Open `http://127.0.0.1:5000`.


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

## Notes
- Keep secrets in `.env` (not committed). Share `.env.example` with dummy values.
- The lint workflow expects Python 3.10 and Pipenv; install deps before running locally.
