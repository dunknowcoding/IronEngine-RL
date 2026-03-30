from __future__ import annotations

from math import atan2, degrees
from typing import Any

from ironengine_rl.interfaces import InferenceResult, ModelProviderPort, Observation


class RuleBasedModelProvider(ModelProviderPort):
    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        sensors = observation.sensors
        object_dx = sensors.get("object_dx", 0.0)
        object_dy = sensors.get("object_dy", 0.0)
        object_distance = (object_dx**2 + object_dy**2) ** 0.5
        heading_error = degrees(atan2(object_dy, max(object_dx, 1e-6)))
        grasp_ready = 1.0 if sensors.get("claw_alignment", 0.0) > 0.85 and object_distance < 0.45 else 0.0
        task_phase = "grasp" if grasp_ready else "approach"
        anomalies: list[str] = []
        if sensors.get("battery_level", 1.0) < 0.15:
            anomalies.append("low_battery")
        if sensors.get("collision_risk", 0.0) > 0.7:
            anomalies.append("collision_risk")
        visual_summary = {
            camera.role: camera.features.get("target_visibility", 0.0)
            for camera in observation.cameras
        }
        return InferenceResult(
            task_phase=task_phase,
            state_estimate={
                "object_distance": object_distance,
                "heading_error_deg": heading_error,
                "grasp_ready": grasp_ready,
                "arm_extension": sensors.get("arm_extension", 0.0),
                "arm_height": sensors.get("arm_height", 0.0),
            },
            reward_hints={
                "distance_progress": max(0.0, 1.0 - object_distance),
                "alignment_bonus": sensors.get("claw_alignment", 0.0),
                "visibility_bonus": sum(visual_summary.values()) / max(len(visual_summary), 1),
            },
            anomalies=anomalies,
            visual_summary=visual_summary,
            notes=context.get("repository_notes", []),
        )
