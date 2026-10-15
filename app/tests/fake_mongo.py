"""A small in-memory stand-in for the Motor collections the services use.

It supports the queries this code actually runs: equality, $in, $nin, $ne, $gte, $lte,
$exists and $or, dotted paths, $set / $inc / $unset / $push updates, upserts, sort and limit.
"""

import copy
import itertools
from typing import Any, Dict, List, Optional

_ids = itertools.count(1)


def _get(doc: Dict[str, Any], path: str) -> Any:
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _set(doc: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _unset(doc: Dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.get(p)
        if not isinstance(cur, dict):
            return
    cur.pop(parts[-1], None)


def _cmp(value: Any, cond: Any) -> bool:
    if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$in" and value not in arg:
                return False
            if op == "$nin" and value in arg:
                return False
            if op == "$ne" and value == arg:
                return False
            if op == "$gte" and (value is None or value < arg):
                return False
            if op == "$lte" and (value is None or value > arg):
                return False
            if op == "$gt" and (value is None or value <= arg):
                return False
            if op == "$lt" and (value is None or value >= arg):
                return False
            if op == "$exists" and (value is not None) != bool(arg):
                return False
        return True
    return value == cond


def matches(doc: Dict[str, Any], query: Optional[Dict[str, Any]]) -> bool:
    for key, cond in (query or {}).items():
        if key == "$or":
            if not any(matches(doc, q) for q in cond):
                return False
            continue
        if not _cmp(_get(doc, key), cond):
            return False
    return True


class Result:
    def __init__(self, matched=0, modified=0, deleted=0, inserted_id=None, upserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.deleted_count = deleted
        self.inserted_id = inserted_id
        self.upserted_id = upserted_id


class Cursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs

    def sort(self, key, direction=None):
        keys = key if isinstance(key, list) else [(key, direction or 1)]
        for field, d in reversed(keys):
            self.docs.sort(key=lambda doc: (_get(doc, field) is None, _get(doc, field)), reverse=d == -1)
        return self

    def limit(self, n: int):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length: Optional[int] = None):
        return self.docs[:length] if length else self.docs


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None, unique: Optional[List[str]] = None):
        # Fields with a unique index: inserting a duplicate raises, as Mongo does.
        self.unique = unique or []
        self.docs: List[Dict[str, Any]] = []
        for d in docs or []:
            d = copy.deepcopy(d)
            d.setdefault("_id", next(_ids))
            self.docs.append(d)

    def _apply(self, doc: Dict[str, Any], update: Dict[str, Any]) -> None:
        for path, value in (update.get("$set") or {}).items():
            _set(doc, path, copy.deepcopy(value))
        for path, value in (update.get("$inc") or {}).items():
            _set(doc, path, (_get(doc, path) or 0) + value)
        for path in (update.get("$unset") or {}):
            _unset(doc, path)
        for path, value in (update.get("$push") or {}).items():
            current = _get(doc, path) or []
            _set(doc, path, current + [copy.deepcopy(value)])

    async def find_one(self, query=None, projection=None, sort=None, **_):
        rows = [d for d in self.docs if matches(d, query)]
        if sort:
            rows = Cursor(rows).sort(sort).docs
        return copy.deepcopy(rows[0]) if rows else None

    def find(self, query=None, projection=None, **_):
        return Cursor([copy.deepcopy(d) for d in self.docs if matches(d, query)])

    async def insert_one(self, doc):
        from pymongo.errors import DuplicateKeyError

        for field in self.unique:
            if any(_get(d, field) == _get(doc, field) for d in self.docs):
                raise DuplicateKeyError(f"duplicate {field}")
        doc.setdefault("_id", next(_ids))
        self.docs.append(copy.deepcopy(doc))
        return Result(inserted_id=doc["_id"])

    async def insert_many(self, docs):
        for d in docs:
            await self.insert_one(d)
        return Result()

    async def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if matches(d, query):
                self._apply(d, update)
                return Result(matched=1, modified=1)
        if upsert:
            doc = {k: v for k, v in query.items() if not k.startswith("$") and not isinstance(v, dict)}
            self._apply(doc, update)
            doc["_id"] = next(_ids)
            self.docs.append(doc)
            return Result(upserted_id=doc["_id"])
        return Result()

    async def update_many(self, query, update):
        n = 0
        for d in self.docs:
            if matches(d, query):
                self._apply(d, update)
                n += 1
        return Result(matched=n, modified=n)

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if matches(d, query):
                del self.docs[i]
                return Result(deleted=1)
        return Result()

    async def delete_many(self, query):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not matches(d, query)]
        return Result(deleted=before - len(self.docs))

    async def create_index(self, *_a, **_k):
        return None


class FakeDB(dict):
    """db["name"] and db.name both work, and unknown collections start empty."""

    def __missing__(self, key):
        self[key] = FakeCollection()
        return self[key]

    def __getattr__(self, key):
        if key.startswith("__"):
            raise AttributeError(key)
        return self[key]
