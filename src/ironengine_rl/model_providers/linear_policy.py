from __future__ import annotations

import json
from math import atan2, degrees
from pathlib import Path
from typing import Any

from ironengine_rl.interfaces import InferenceResult, ModelProviderPort, Observation


class LinearPolicyProvider(ModelProviderPort):
    def __init__(self, profile: dict[str, Any]) -> None:
        provider_cfg = profile.get("model_provider", {})
        self.threshold = float(provider_cfg.get("grasp_threshold", 0.35))
        self.weights = self._load_weights(provider_cfg)

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        sensors = observation.sensors
        object_dx = float(sensors.get("object_dx", 0.0))
        object_dy = float(sensors.get("object_dy", 0.0))
        object_distance = (object_dx**2 + object_dy**2) ** 0.5
        heading_error = degrees(atan2(object_dy, max(object_dx, 1e-6)))
        visibility = sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras) / max(len(observation.cameras), 1)
        features = {
            "bias": 1.0,
            "object_distance": object_distance,
            "heading_error_abs": abs(heading_error),
            "claw_alignment": float(sensors.get("claw_alignment", 0.0)),
            "pregrasp_ready": float(sensors.get("pregrasp_ready", 0.0)),
            "target_reachable": float(sensors.get("target_reachable", 0.0)),
            "visibility": visibility,
            "battery_level": float(sensors.get("battery_level", 1.0)),
            "collision_risk": float(sensors.get("collision_risk", 0.0)),
            "arm_extension": float(sensors.get("arm_extension", 0.0)),
            "arm_height": float(sensors.get("arm_height", 0.0)),
        }
        grasp_score = self._score(features)
        grasp_ready = 1.0 if grasp_score >= self.threshold else 0.0
        task_phase = "grasp" if grasp_ready else "approach"
        anomalies: list[str] = []
        if features["battery_level"] < 0.15:
            anomalies.append("low_battery")
        if features["collision_risk"] > 0.7:
            anomalies.append("collision_risk")
        visual_summary = {camera.role: camera.features.get("target_visibility", 0.0) for camera in observation.cameras}
        return InferenceResult(
            task_phase=task_phase,
            state_estimate={
                "object_distance": object_distance,
                "heading_error_deg": heading_error,
                "grasp_ready": grasp_ready,
                "policy_score": grasp_score,
                "arm_extension": features["arm_extension"],
                "arm_height": features["arm_height"],
            },
            reward_hints={
                "distance_progress": max(0.0, 1.0 - object_distance),
                "alignment_bonus": features["claw_alignment"],
                "visibility_bonus": visibility,
                "pregrasp_bonus": features["pregrasp_ready"],
            },
            anomalies=anomalies,
            visual_summary=visual_summary,
            notes=context.get("repository_notes", []),
        )

    def _score(self, features: dict[str, float]) -> float:
        total = 0.0
        for name, value in features.items():
            total += float(self.weights.get(name, 0.0)) * value
        return total

    @staticmethod
    def _load_weights(provider_cfg: dict[str, Any]) -> dict[str, float]:
        if "weights" in provider_cfg:
            return {key: float(value) for key, value in provider_cfg["weights"].items()}
        if weights_file := provider_cfg.get("weights_file"):
            payload = json.loads(Path(weights_file).read_text(encoding="utf-8"))
            return {key: float(value) for key, value in payload.items()}
        return {
            "bias": -0.1,
            "object_distance": -0.55,
            "heading_error_abs": -0.012,
            "claw_alignment": 0.7,
            "pregrasp_ready": 0.9,
            "target_reachable": 0.35,
            "visibility": 0.25,
            "battery_level": 0.08,
            "collision_risk": -0.4,
            "arm_extension": 0.18,
            "arm_height": -0.08,
        }