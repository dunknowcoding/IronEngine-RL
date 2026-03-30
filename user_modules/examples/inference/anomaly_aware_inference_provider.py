from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.interfaces import InferenceResult, Observation
from ironengine_rl.model_providers.rule_based import RuleBasedModelProvider


@dataclass(slots=True)
class AnomalyAwareInferenceProvider:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    fallback: RuleBasedModelProvider = field(default_factory=RuleBasedModelProvider)

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        fallback = self.fallback.infer(observation, context)
        cfg = self.config or {}
        anomalies = list(fallback.anomalies)
        visibility_threshold = float(cfg.get("visibility_alert_threshold", 0.35))
        collision_threshold = float(cfg.get("collision_anomaly_threshold", 0.65))
        battery_threshold = float(cfg.get("battery_alert_threshold", 0.2))
        expected_cameras = int(cfg.get("expected_camera_count", 2))
        visibility = sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras) / max(len(observation.cameras), 1)
        if len(observation.cameras) < expected_cameras:
            anomalies.append("camera_dropout")
        if visibility < visibility_threshold:
            anomalies.append(str(cfg.get("visibility_anomaly_name", "visibility_below_threshold")))
        if float(observation.sensors.get("collision_risk", 0.0)) >= collision_threshold:
            anomalies.append(str(cfg.get("collision_anomaly_name", "collision_watch")))
        if float(observation.sensors.get("battery_level", 1.0)) <= battery_threshold:
            anomalies.append(str(cfg.get("battery_anomaly_name", "battery_margin_low")))
        if observation.metadata.get("fault_window_active"):
            anomalies.append(str(cfg.get("fault_anomaly_name", "fault_window_active")))
        deduped = list(dict.fromkeys(anomalies))
        notes = list(fallback.notes)
        notes.append("Anomaly-aware inference provider active.")
        notes.append(f"Anomalies: {', '.join(deduped) if deduped else 'none'}")
        return InferenceResult(
            task_phase=fallback.task_phase,
            state_estimate={**fallback.state_estimate, "visibility_score": float(visibility)},
            reward_hints=dict(fallback.reward_hints),
            anomalies=deduped,
            visual_summary={**fallback.visual_summary, "average_visibility": float(visibility)},
            notes=notes,
        )
