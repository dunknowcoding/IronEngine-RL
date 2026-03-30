from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, StepResult


@dataclass(slots=True)
class TaskMetricsAccumulator:
    total_steps: int = 0
    approach_steps: int = 0
    aligned_steps: int = 0
    grasp_events: int = 0
    collision_events: int = 0
    low_battery_events: int = 0
    safety_interventions: int = 0
    total_energy: float = 0.0
    visibility_sum: float = 0.0
    best_alignment: float = 0.0
    min_object_distance: float | None = None

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        self.total_steps += 1
        observation = step_result.observation
        sensors = observation.sensors
        if step_result.info.get("phase_hint") == "approach":
            self.approach_steps += 1
        alignment = float(sensors.get("claw_alignment", 0.0))
        self.best_alignment = max(self.best_alignment, alignment)
        if alignment >= 0.85:
            self.aligned_steps += 1
        if float(sensors.get("object_grasped", 0.0)) > 0.5:
            self.grasp_events += 1
        if float(sensors.get("collision_risk", 0.0)) >= 0.8:
            self.collision_events += 1
        if float(sensors.get("battery_level", 1.0)) < 0.2:
            self.low_battery_events += 1
        if action.auxiliary.get("safety_stop") or action.auxiliary.get("safety_clamped"):
            self.safety_interventions += 1
        distance = sensors.get("object_distance")
        if isinstance(distance, (int, float)):
            numeric_distance = float(distance)
            self.min_object_distance = numeric_distance if self.min_object_distance is None else min(self.min_object_distance, numeric_distance)
        if observation.cameras:
            average_visibility = sum(frame.features.get("target_visibility", 0.0) for frame in observation.cameras) / len(observation.cameras)
            self.visibility_sum += average_visibility
        self.total_energy += sum(
            abs(value)
            for value in [
                action.chassis_forward,
                action.chassis_strafe,
                action.chassis_turn,
                action.arm_lift,
                action.arm_extend,
                action.wrist_yaw,
                action.gripper_close,
            ]
        )

    def to_summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        steps = max(self.total_steps, 1)
        return {
            "total_steps": self.total_steps,
            "approach_ratio": self.approach_steps / steps,
            "alignment_ratio": self.aligned_steps / steps,
            "grasp_event_ratio": self.grasp_events / steps,
            "collision_events": self.collision_events,
            "low_battery_events": self.low_battery_events,
            "safety_interventions": self.safety_interventions,
            "average_visibility": self.visibility_sum / steps,
            "average_energy": self.total_energy / steps,
            "average_reward_per_step": reward_total / steps,
            "episode_efficiency": successes / steps,
            "best_alignment": self.best_alignment,
            "minimum_object_distance": self.min_object_distance,
            "success_rate": successes / episodes if episodes else 0.0,
        }
