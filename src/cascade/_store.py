"""
Checkpoint store — lightweight JSON persistence for C₃/C₄/linkage state.

Replaces the original hermes-securer CheckpointManager dependency
with a simple file-based store. Zero external dependencies.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class Store:
    """Simple JSON file-based checkpoint persistence."""

    def __init__(self, store_dir: Optional[str] = None):
        self.store_dir = Path(store_dir or Path.home() / ".cascade" / "checkpoints")
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, state: dict) -> bool:
        """Save checkpoint state to a JSON file."""
        path = self.store_dir / f"{name}.json"
        state["_saved_at"] = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(state, f, default=str, indent=2)
        return True

    def load(self, name: str) -> Optional[dict]:
        """Load checkpoint state from a JSON file. Returns None if not found."""
        path = self.store_dir / f"{name}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def delete(self, name: str) -> bool:
        """Delete a checkpoint file."""
        path = self.store_dir / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_checkpoints(self) -> list[str]:
        """List all stored checkpoint names."""
        return [p.stem for p in self.store_dir.glob("*.json")]

    def clear_all(self):
        """Delete all checkpoints."""
        for p in self.store_dir.glob("*.json"):
            p.unlink()
