"""Mongo connection helper.

In normal environments this connects to Atlas. In CI or when secrets are
missing/invalid we fall back to in-memory collections so tests run without auth.
"""

# pylint: disable=missing-function-docstring,invalid-name

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv
from pymongo.errors import OperationFailure
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()


class FakeCursor:
    """Very small subset of pymongo cursor used in tests."""

    def __init__(self, docs: Iterable[Dict[str, Any]]):
        self.docs: List[Dict[str, Any]] = list(docs)

    def sort(self, key: str, direction: int) -> "FakeCursor":
        reverse = bool(direction and direction < 0)
        self.docs.sort(key=lambda d: d.get(key), reverse=reverse)
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    """In-memory replacement for a MongoDB collection."""

    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []

    def insert_one(self, doc: Dict[str, Any]) -> Dict[str, int]:
        self.docs.append(doc)
        return {"inserted_id": len(self.docs) - 1}

    def insert_many(self, docs: Iterable[Dict[str, Any]]) -> Dict[str, List[int]]:
        docs = list(docs)
        start = len(self.docs)
        self.docs.extend(docs)
        return {"inserted_ids": list(range(start, start + len(docs)))}

    def delete_many(self, _filter: Dict[str, Any]) -> Dict[str, int]:
        deleted = len(self.docs)
        self.docs = []
        return {"deleted_count": deleted}

    def find_one(self, sort=None) -> Dict[str, Any] | None:
        if not self.docs:
            return None
        docs = list(self.docs)
        if sort:
            key, direction = sort[0]
            reverse = bool(direction and direction < 0)
            docs.sort(key=lambda d: d.get(key), reverse=reverse)
        return docs[0]

    def find(self, query: Dict[str, Any] | None = None) -> FakeCursor:
        docs = list(self.docs)
        if query and "ts" in query:
            gte = query["ts"].get("$gte")
            if gte is not None:
                docs = [d for d in docs if d.get("ts", datetime.min) >= gte]
        return FakeCursor(docs)

    def create_index(self, *_args, **_kwargs) -> None:
        return None


USERNAME = os.getenv("MONGO_USERNAME")
PASSWORD = os.getenv("MONGO_PASSWORD")
APP_NAME = os.getenv("APP_NAME")
MONGO_DB = os.getenv("MONGO_DB", "posture")

use_fake = not (USERNAME and PASSWORD and APP_NAME)

if use_fake:
    samples = FakeCollection()
    events = FakeCollection()
else:
    URI = f"mongodb+srv://{USERNAME}:{PASSWORD}@ribs.xo4actr.mongodb.net/?appName={APP_NAME}"
    client = MongoClient(URI, server_api=ServerApi("1"))
    db = client[MONGO_DB]
    samples = db["samples"]
    events = db["events"]

    try:
        client.admin.command("ping")
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except OperationFailure as exc:  # pragma: no cover
        print(exc)
        samples = FakeCollection()
        events = FakeCollection()
