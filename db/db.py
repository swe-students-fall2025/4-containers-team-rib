"""Mongo connection helper."""

# pylint: disable=mixed-line-endings
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("MONGO_USERNAME")
PASSWORD = os.getenv("MONGO_PASSWORD")
APP_NAME = os.getenv("APP_NAME")
MONGO_DB = os.getenv("MONGO_DB", "posture")

uri = (
    f"mongodb+srv://{USERNAME}:{PASSWORD}@ribs.xo4actr.mongodb.net/?appName={APP_NAME}"
)

client = MongoClient(uri, server_api=ServerApi("1"))
db = client[MONGO_DB]

# collections created
samples = db["samples"]
events = db["events"]


try:
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:  # pylint: disable=broad-exception-caught
    print(e)
