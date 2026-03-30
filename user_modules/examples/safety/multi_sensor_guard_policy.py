from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.core.safety import SafetyController
from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class MultiSensorGuardSafetyPolicy:
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
        sensors = observation.sensors

        front_range = float(sensors.get("front_range_m", 1.0))
        stop_gesture = float(sensors.get("operator_stop_gesture", 0.0))
        gesture_confidence = float(sensors.get("gesture_confidence", 0.0))
        air_quality = float(sensors.get("air_quality_index", 0.0))
        motor_temp = float(sensors.get("motor_temp_c", 0.0))

        front_range_stop_threshold = float(cfg.get("front_range_stop_threshold_m", 0.2))
        stop_gesture_threshold = float(cfg.get("stop_gesture_threshold", 0.5))
        gesture_conf_threshold = float(cfg.get("gesture_confidence_threshold", 0.7))
        air_quality_warn_threshold = float(cfg.get("air_quality_warn_threshold", 150.0))
        motor_temp_warn_threshold = float(cfg.get("motor_temp_warn_threshold_c", 65.0))

        if stop_gesture >= stop_gesture_threshold and gesture_confidence >= gesture_conf_threshold:
            auxiliary = dict(safe_action.auxiliary)
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_gesture_stop"] = 1.0
            return ActionCommand(auxiliary=auxiliary)

        if front_range <= front_range_stop_threshold:
            auxiliary = dict(safe_action.auxiliary)
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_front_range"] = 1.0
            return ActionCommand(auxiliary=auxiliary)

        if air_quality >= air_quality_warn_threshold:
            safe_action.auxiliary["air_quality_warning"] = 1.0
        if motor_temp >= motor_temp_warn_threshold:
            safe_action.auxiliary["motor_temp_warning"] = 1.0
            safe_action.arm_lift = min(safe_action.arm_lift, 0.0)
            safe_action.arm_extend = min(safe_action.arm_extend, 0.0)

        return safe_action