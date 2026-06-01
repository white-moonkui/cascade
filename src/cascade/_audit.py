"""
Audit trail — structured JSONL logging of every guard() decision.

Hash-chained integrity: every record links to its predecessor via
SHA-256, forming an append-only tamper-evident chain.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

_GENESIS_HASH = "0" * 64


def _canonical_json(obj: dict) -> str:
    """Deterministic JSON with sorted keys — ensures hash reproducibility."""
    return json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)


def _compute_hash(entry: dict) -> str:
    """SHA-256 of the canonical entry (excluding the 'hash' field itself)."""
    clone = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(_canonical_json(clone).encode()).hexdigest()


class AuditTrail:
    """Append-only JSONL audit log with SHA-256 chain integrity.

    Each guard() call appends one JSON line to the trail file.
    Every record carries:
      - ``prev_hash`` — SHA-256 of the preceding record (or 64 zeros for the
        genesis entry)
      - ``hash`` — SHA-256 of the current record's canonical JSON
    """

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or Path.home() / ".cascade" / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, entry: dict) -> str:
        """Append a new audit record with chain integrity.

        Automatically sets ``audit_id``, ``timestamp``, ``prev_hash``,
        and ``hash``.
        """
        entry["audit_id"] = entry.get("audit_id") or uuid4().hex[:12]
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["prev_hash"] = self._last_hash()

        entry_hash = _compute_hash(entry)
        entry["hash"] = entry_hash

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
        return entry["audit_id"]

    def verify(self) -> dict:
        """Walk the full chain and verify hash integrity.

        Returns a dict with:
          - ``valid``  — ``True`` if the chain is intact
          - ``entries`` — total entries scanned
          - ``first_broken`` — index (1-based) of first tampered record, or ``None``
          - ``errors`` — list of human-readable error messages
        """
        result = {"valid": True, "entries": 0, "first_broken": None, "errors": []}
        if not self.path.exists():
            result["errors"].append("Audit file does not exist")
            result["valid"] = False
            return result

        expected_prev = _GENESIS_HASH
        with open(self.path, encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError as e:
                    result["valid"] = False
                    if result["first_broken"] is None:
                        result["first_broken"] = idx
                    result["errors"].append(f"Line {idx}: invalid JSON — {e}")
                    continue

                result["entries"] = idx

                # Check prev_hash
                stored_prev = entry.get("prev_hash", "")
                if stored_prev != expected_prev:
                    result["valid"] = False
                    if result["first_broken"] is None:
                        result["first_broken"] = idx
                    result["errors"].append(
                        f"Line {idx}: prev_hash mismatch "
                        f"(expected {expected_prev[:12]}…, got {stored_prev[:12]}…)"
                    )

                # Check hash
                stored_hash = entry.get("hash", "")
                computed_hash = _compute_hash(entry)
                if stored_hash != computed_hash:
                    result["valid"] = False
                    if result["first_broken"] is None:
                        result["first_broken"] = idx
                    result["errors"].append(
                        f"Line {idx}: hash mismatch "
                        f"(expected {computed_hash[:12]}…, got {stored_hash[:12]}…)"
                    )

                expected_prev = stored_hash

        return result

    def recent(self, limit: int = 10) -> list[dict]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    entries.append(json.loads(stripped))
        return entries[-limit:]

    def query(
        self,
        *,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        if not self.path.exists():
            return []
        results = []
        with open(self.path, encoding="utf-8") as f:
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _last_hash(self) -> str:
        """Return the ``hash`` of the last record, or genesis hash if empty."""
        if not self.path.exists():
            return _GENESIS_HASH
        try:
            with open(self.path, encoding="utf-8") as f:
                non_empty = [l for l in f.read().splitlines() if l.strip()]
                if not non_empty:
                    return _GENESIS_HASH
                last_entry = json.loads(non_empty[-1])
                return last_entry.get("hash", _GENESIS_HASH)
        except (OSError, json.JSONDecodeError):
            return _GENESIS_HASH
