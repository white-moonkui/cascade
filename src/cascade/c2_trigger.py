"""
C₂ — Trigger Engine.

Evaluates trigger rules that fire actions when conditions are met.
Independent module — no internal cascade imports, no checkpoint store.
"""

from typing import Any, Optional, Callable
from datetime import datetime
import enum
import threading


class TriggerStatus(enum.Enum):
    IDLE = "idle"
    FIRING = "firing"
    FIRED = "fired"
    FAILED = "failed"


TriggerAction = Callable[[dict], Any]


class TriggerEngine:
    """
    Evaluates trigger rules against state snapshots.

    A trigger fires when its ``condition`` callback returns ``True``
    for the current context. Fired triggers call their ``action``
    callback and record status.
    """

    def __init__(self):
        self._triggers: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        condition: Callable[[dict], bool],
        action: Optional[TriggerAction] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        with self._lock:
            self._triggers[name] = {
                "name": name,
                "condition": condition,
                "action": action,
                "metadata": metadata or {},
                "status": TriggerStatus.IDLE,
                "last_fired": None,
                "fire_count": 0,
            }
        return name

    def evaluate(self, context: dict) -> list[dict]:
        """Evaluate all registered triggers and fire those whose condition passes."""
        fired: list[dict] = []
        with self._lock:
            for name, t in self._triggers.items():
                try:
                    if t["condition"](context):
                        t["status"] = TriggerStatus.FIRING
                        t["fire_count"] += 1
                        t["last_fired"] = datetime.now().isoformat()
                        result = None
                        if t["action"]:
                            result = t["action"](context)
                        t["status"] = TriggerStatus.FIRED
                        fired.append(
                            {
                                "name": name,
                                "status": "fired",
                                "fire_count": t["fire_count"],
                                "last_fired": t["last_fired"],
                                "result": result,
                            }
                        )
                except Exception as exc:
                    t["status"] = TriggerStatus.FAILED
                    fired.append(
                        {
                            "name": name,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
        return fired

    def reset(self, name: str):
        with self._lock:
            if name in self._triggers:
                t = self._triggers[name]
                t["status"] = TriggerStatus.IDLE
                t["last_fired"] = None

    def reset_all(self):
        with self._lock:
            for t in self._triggers.values():
                t["status"] = TriggerStatus.IDLE
                t["last_fired"] = None

    def remove(self, name: str):
        with self._lock:
            self._triggers.pop(name, None)

    def summary(self) -> dict:
        with self._lock:
            return {
                "module": "C2 (Trigger)",
                "trigger_count": len(self._triggers),
                "triggers": {
                    n: {
                        "status": t["status"].value,
                        "fire_count": t["fire_count"],
                        "last_fired": t["last_fired"],
                    }
                    for n, t in self._triggers.items()
                },
            }
