from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class SafetyController:
    profile: dict[str, Any]
    last_timestamp_s: float | None = None
    stale_steps: int = 0

    def reset(self) -> None:
        self.last_timestamp_s = None
        self.stale_steps = 0

    def apply(self, action: ActionCommand, observation: Observation, inference: InferenceResult) -> ActionCommand:
        limits = self.profile.get("safety", {})
        max_chassis = float(limits.get("max_chassis_speed", 0.8))
        max_turn = float(limits.get("max_turn_rate", 0.7))
        max_arm = float(limits.get("max_arm_speed", 0.8))
        max_extension = float(limits.get("max_arm_extension", 0.85))
        max_gripper_close = float(limits.get("max_gripper_close", 1.0))
        low_battery_stop = float(limits.get("low_battery_stop_threshold", 0.15))
        stale_limit = int(limits.get("stale_observation_stop_steps", 3))
        require_connection = bool(limits.get("connection_required", True))
        collision_risk = float(observation.sensors.get("collision_risk", 0.0))
        battery_level = float(observation.sensors.get("battery_level", 1.0))
        connection_alive = float(observation.sensors.get("connection_alive", 1.0))
        arm_extension = float(observation.sensors.get("arm_extension", 0.0))
        gripper_state = float(observation.sensors.get("gripper_close", 0.0))
        auxiliary = dict(action.auxiliary)
        self._update_staleness(observation.timestamp_s)
        if collision_risk > float(limits.get("collision_stop_threshold", 0.95)):
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_collision"] = 1.0
            return ActionCommand(gripper_close=self._clamp(action.gripper_close, -1.0, 1.0), auxiliary=auxiliary)
        if require_connection and connection_alive < 0.5:
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_connection"] = 1.0
            return ActionCommand(auxiliary=auxiliary)
        if stale_limit and self.stale_steps >= stale_limit:
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_stale"] = 1.0
            return ActionCommand(auxiliary=auxiliary)
        if battery_level <= low_battery_stop or "low_battery" in inference.anomalies:
            auxiliary["safety_stop"] = 1.0
            auxiliary["safety_reason_battery"] = 1.0
            return ActionCommand(gripper_close=self._clamp(action.gripper_close, -1.0, 1.0), auxiliary=auxiliary)

        safe_action = ActionCommand(
            chassis_forward=self._clamp(action.chassis_forward, -max_chassis, max_chassis),
            chassis_strafe=self._clamp(action.chassis_strafe, -max_chassis, max_chassis),
            chassis_turn=self._clamp(action.chassis_turn, -max_turn, max_turn),
            arm_lift=self._clamp(action.arm_lift, -max_arm, max_arm),
            arm_extend=self._clamp(action.arm_extend, -max_arm, max_arm),
            wrist_yaw=self._clamp(action.wrist_yaw, -max_arm, max_arm),
            gripper_close=self._clamp(action.gripper_close, -1.0, 1.0),
            auxiliary=auxiliary,
        )
        clamped = safe_action != action
        if arm_extension >= max_extension and safe_action.arm_extend > 0.0:
            safe_action.arm_extend = 0.0
            clamped = True
        if gripper_state >= max_gripper_close and safe_action.gripper_close > 0.0:
            safe_action.gripper_close = 0.0
            clamped = True
        if clamped:
            safe_action.auxiliary["safety_clamped"] = 1.0
        return safe_action

    def _update_staleness(self, timestamp_s: float) -> None:
        if self.last_timestamp_s is None or timestamp_s != self.last_timestamp_s:
            self.last_timestamp_s = timestamp_s
            self.stale_steps = 0
            return
        self.stale_steps += 1

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
