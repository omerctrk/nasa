"""Canonical JSON snapshot hashing shared by preparation and worker code."""

import hashlib
import json


class InvalidSnapshot(Exception):
    pass


def snapshot_hash(snapshot: dict) -> str:
    if not isinstance(snapshot, dict):
        raise InvalidSnapshot()
    try:
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise InvalidSnapshot() from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
