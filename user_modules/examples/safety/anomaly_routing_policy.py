from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.core.safety import SafetyController
from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class AnomalyRoutingSafetyPolicy:
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
        cfg = self.config or {}
        stop_anomalies = {str(item) for item in cfg.get("stop_anomalies", ["fault_window_active", "camera_dropout"]) }
        warn_only_anomalies = {str(item) for item in cfg.get("warn_only_anomalies", ["visibility_below_threshold", "collision_watch"]) }
        active = {str(item) for item in inference.anomalies}
        stop_hits = sorted(active & stop_anomalies)
        warn_hits = sorted(active & warn_only_anomalies)
        if stop_hits:
            auxiliary = dict(safe_action.auxiliary)
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_anomaly"] = 1.0
            auxiliary["anomaly_stop_count"] = float(len(stop_hits))
            auxiliary["anomaly_stop_names"] = ",".join(stop_hits)
            return ActionCommand(auxiliary=auxiliary)
        if warn_hits:
            safe_action.auxiliary["anomaly_warning"] = 1.0
            safe_action.auxiliary["anomaly_warning_names"] = ",".join(warn_hits)
        return safe_action
