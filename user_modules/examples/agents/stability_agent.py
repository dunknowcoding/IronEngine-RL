from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class StabilityAgent:
    profile: dict[str, Any]
    config: dict[str, Any] | None = None

    def act(self, observation: Observation, inference: InferenceResult, repository_context: dict[str, Any]) -> ActionCommand:
        collision_risk = float(observation.sensors.get("collision_risk", 0.0))
        extension = float(observation.sensors.get("arm_extension", 0.0))
        if collision_risk > 0.8:
            return ActionCommand(chassis_forward=0.0, chassis_turn=0.0, arm_extend=0.0)
        reach_bias = 0.2 if float(inference.reward_hints.get("progress", 0.0)) > 0.0 else 0.1
        return ActionCommand(
            chassis_forward=0.15 if collision_risk < 0.2 else 0.0,
            arm_extend=0.1 if extension < 0.5 else 0.0,
            arm_lift=reach_bias,
            gripper_close=0.1,
        )
