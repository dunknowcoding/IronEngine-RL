from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import InferenceResult, Observation


@dataclass(slots=True)
class VisionlessInferenceProvider:
    profile: dict[str, Any]
    config: dict[str, Any] | None = None

    def infer(self, observation: Observation, repository_context: dict[str, Any]) -> InferenceResult:
        battery_level = float(observation.sensors.get("battery_level", 1.0))
        collision_risk = float(observation.sensors.get("collision_risk", 0.0))
        return InferenceResult(
            task_phase="link_validation",
            state_estimate={
                "arm_extension": float(observation.sensors.get("arm_extension", 0.0)),
                "arm_height": float(observation.sensors.get("arm_height", 0.0)),
                "grasp_ready": 0.0,
            },
            reward_hints={
                "progress": 1.0 if collision_risk < 0.5 and battery_level > 0.2 else 0.0,
            },
            anomalies=["low_battery"] if battery_level < 0.2 else [],
            notes=["Visionless provider active"],
        )
