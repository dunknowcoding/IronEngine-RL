from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class ARMSmartActionSchemeAgent:
    profile: dict[str, Any]
    config: dict[str, Any] | None = None

    def act(self, observation: Observation, inference: InferenceResult, repository_context: dict[str, Any]) -> ActionCommand:
        sensors = observation.sensors
        state = inference.state_estimate
        scheme = repository_context.get("action_scheme", {})
        command = ActionCommand()
        command.action_scheme = str(scheme.get("name", "direct_channel_control"))

        if float(sensors.get("collision_risk", 0.0)) > 0.75:
            command.auxiliary["policy_phase"] = "hold"
            return command

        object_distance = float(state.get("object_distance", 1.0))
        heading_error = float(state.get("heading_error_deg", 0.0))
        grasp_confidence = float(state.get("grasp_confidence", state.get("policy_score", 0.0)))
        arm_extension = float(sensors.get("arm_extension", 0.0))
        gripper_close = float(sensors.get("gripper_close", 0.0))

        if object_distance > 0.35:
            command.chassis_forward = 0.16
            command.chassis_turn = max(-0.2, min(0.2, -heading_error / 45.0))
            command.arm_lift = 0.08
            command.auxiliary["policy_phase"] = "approach"
        elif grasp_confidence < 0.55:
            command.arm_extend = 0.1 if arm_extension < 0.6 else 0.0
            command.wrist_yaw = max(-0.15, min(0.15, -heading_error / 60.0))
            command.arm_lift = 0.05
            command.auxiliary["policy_phase"] = "pregrasp"
        else:
            command.arm_extend = 0.05 if arm_extension < 0.72 else 0.0
            command.gripper_close = 0.7 if gripper_close < 0.9 else 0.0
            command.arm_lift = 0.12 if float(sensors.get("object_grasped", 0.0)) > 0.5 else 0.04
            command.auxiliary["policy_phase"] = "grasp_or_lift"

        command.auxiliary["schedule_notes_used"] = 1.0 if scheme.get("schedule_notes") else 0.0
        return command
