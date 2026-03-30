from __future__ import annotations

from typing import Any

from ironengine_rl.evaluations.base import EvaluationTaskDefinition
from ironengine_rl.framework.boundaries import compute_boundary_conditions


def build_armsmart_pick_place_task(profile: dict[str, Any], config: dict[str, Any] | None = None) -> EvaluationTaskDefinition:
    task_cfg = config or {}
    task_name = str(task_cfg.get("name", "armsmart_pick_place_real_task"))
    required_fields = list(
        task_cfg.get(
            "required_observation_fields",
            [
                "connection_alive",
                "battery_level",
                "collision_risk",
                "object_dx",
                "object_dy",
                "claw_alignment",
                "arm_extension",
                "arm_height",
                "gripper_close",
            ],
        )
    )
    interface_requirements = {
        "camera_roles": ["dash", "claw"],
        "action_channels": ["chassis_forward", "chassis_turn", "arm_lift", "arm_extend", "wrist_yaw", "gripper_close"],
        "action_scheme": profile.get("action_scheme", {}),
        "repository_keys": ["knowledge_repository", "database", "action_scheme", "recent_reward_summary", "state_summary"],
    }
    return EvaluationTaskDefinition(
        name=task_name,
        description="ARMSmart pick-and-place task with explicit approach, pregrasp, grasp, lift, and place phases.",
        success_signal=str(task_cfg.get("success_signal", "object_grasped > 0.5 and gripper_close > 0.7 and collision_risk < 0.4")),
        required_observation_fields=required_fields,
        boundary_conditions=compute_boundary_conditions(profile),
        interface_requirements=interface_requirements,
    )
