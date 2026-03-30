from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.core.safety import SafetyController
from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class ConnectionAwareSafetyPolicy:
    profile: dict[str, Any]
    config: dict[str, Any] | None = None
    base: SafetyController | None = None

    def __post_init__(self) -> None:
        self.base = SafetyController(self.profile)

    def reset(self) -> None:
        assert self.base is not None
        self.base.reset()

    def apply(self, action: ActionCommand, observation: Observation, inference: InferenceResult) -> ActionCommand:
        assert self.base is not None
        safe_action = self.base.apply(action, observation, inference)
        connection_alive = float(observation.sensors.get("connection_alive", 1.0))
        if connection_alive < float((self.config or {}).get("connection_hold_threshold", 0.6)):
            safe_action.auxiliary["connection_hold"] = 1.0
            safe_action.chassis_forward = 0.0
            safe_action.chassis_strafe = 0.0
            safe_action.chassis_turn = 0.0
        return safe_action
