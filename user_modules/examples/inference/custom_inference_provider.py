from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import InferenceResult, Observation


@dataclass(slots=True)
class CustomInferenceProvider:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        sensors = observation.sensors
        distance = float(sensors.get("object_distance", sensors.get("object_dx", 0.0)))
        grasp_ready = 1.0 if float(sensors.get("claw_alignment", 0.0)) > 0.6 else 0.0
        return InferenceResult(
            task_phase="grasp" if grasp_ready > 0.5 else "approach",
            state_estimate={
                "object_distance": distance,
                "heading_error_deg": float(sensors.get("heading_error_deg", 0.0)),
                "grasp_ready": grasp_ready,
                "arm_extension": float(sensors.get("arm_extension", 0.0)),
                "arm_height": float(sensors.get("arm_height", 0.0)),
            },
            reward_hints={
                "distance_progress": max(0.0, 1.0 - distance),
                "alignment_bonus": float(sensors.get("claw_alignment", 0.0)),
            },
            notes=["Custom inference provider loaded from organized user_modules examples."],
        )
