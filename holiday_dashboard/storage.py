"""Simple JSON based persistence for the leave management app."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict


_STATE_LOCK = Lock()
_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "state.json"


def _ensure_storage_file() -> None:
    """Create the directory tree for the storage file if necessary."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _STATE_FILE.exists():
        with _STATE_LOCK:
            if not _STATE_FILE.exists():
                _STATE_FILE.write_text(json.dumps({"employees": {}, "applications": {}}), encoding="utf-8")


def load_state() -> Dict[str, Any]:
    """Load and return the current application state."""
    _ensure_storage_file()
    with _STATE_LOCK:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    return data


def save_state(state: Dict[str, Any]) -> None:
    """Persist the application state to disk."""
    _ensure_storage_file()
    with _STATE_LOCK:
        temp_path = _STATE_FILE.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(_STATE_FILE)


__all__ = ["load_state", "save_state"]
