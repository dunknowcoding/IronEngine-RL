from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation


@dataclass(slots=True)
class HeuristicAgent:
    profile: dict[str, Any]

    def act(self, observation: Observation, inference: InferenceResult, repository_context: dict[str, Any]) -> ActionCommand:
        state = inference.state_estimate
        distance = state.get("object_distance", 0.0)
        heading_error = state.get("heading_error_deg", 0.0)
        grasp_ready = state.get("grasp_ready", 0.0) > 0.5
        arm_extension = state.get("arm_extension", 0.0)
        arm_height = state.get("arm_height", 0.0)
        if grasp_ready:
            return ActionCommand(
                arm_extend=0.3 if arm_extension < 0.78 else 0.0,
                arm_lift=0.2 if arm_height < 0.3 else 0.0,
                gripper_close=1.0,
            )
        turn = 0.0
        if abs(heading_error) > 4.0:
            turn = 0.5 if heading_error > 0 else -0.5
        forward = 0.7 if distance > 0.38 else 0.0
        extend = 0.7 if distance <= 0.6 and arm_extension < 0.72 else 0.0
        lift = 0.25 if arm_height < 0.28 else 0.0
        return ActionCommand(
            chassis_forward=forward,
            chassis_turn=turn,
            arm_extend=extend,
            arm_lift=lift,
            wrist_yaw=0.25 if heading_error > 8 else (-0.25 if heading_error < -8 else 0.0),
            gripper_close=0.3 if distance < 0.18 else 0.0,
        )
