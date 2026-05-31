"""
Audit trail — structured JSONL logging of every guard() decision.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4


class AuditTrail:
    """Append-only JSONL audit log for decision governance.

    Each guard() call appends one JSON line to the trail file.
    Supports querying recent decisions by tool name or status.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or Path.home() / ".cascade" / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: dict) -> str:
        audit_id = entry.get("audit_id") or uuid4().hex[:12]
        entry["audit_id"] = audit_id
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return audit_id

    def recent(self, limit: int = 10) -> list[dict]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    entries.append(json.loads(stripped))
        return entries[-limit:]

    def query(self, *, tool_name: Optional[str] = None, status: Optional[str] = None, limit: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        results = []
        with open(self.path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                entry = json.loads(stripped)
                if tool_name and entry.get("tool_name") != tool_name:
                    continue
                if status and entry.get("status") != status:
                    continue
                results.append(entry)
        return results[-limit:]

    def clear(self):
        if self.path.exists():
            self.path.unlink()
