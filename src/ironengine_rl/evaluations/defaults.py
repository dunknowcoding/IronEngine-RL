from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.core.task_metrics import TaskMetricsAccumulator
from ironengine_rl.evaluations.base import EvaluationMetric, EvaluationSuite, EvaluationTaskDefinition
from ironengine_rl.framework.boundaries import compute_boundary_conditions
from ironengine_rl.interfaces import ActionCommand, StepResult
from ironengine_rl.plugins import describe_plugin_spec, instantiate_plugin


@dataclass(slots=True)
class TaskPerformanceMetric(EvaluationMetric):
    name: str = "task_performance"
    accumulator: TaskMetricsAccumulator = field(default_factory=TaskMetricsAccumulator)

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        self.accumulator.update(action, step_result)

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        return self.accumulator.to_summary(episodes=episodes, successes=successes, reward_total=reward_total)


@dataclass(slots=True)
class BoundaryViolationMetric(EvaluationMetric):
    profile: dict[str, Any]
    name: str = "boundary_violations"
    violations: dict[str, int] | None = None

    def __post_init__(self) -> None:
        self.violations = {"collision": 0, "battery": 0, "missing_fields": 0}

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        assert self.violations is not None
        sensors = step_result.observation.sensors
        boundaries = compute_boundary_conditions(self.profile)
        if float(sensors.get("collision_risk", 0.0)) >= boundaries["safety_thresholds"]["collision_stop_threshold"]:
            self.violations["collision"] += 1
        if float(sensors.get("battery_level", 1.0)) <= boundaries["safety_thresholds"]["low_battery_stop_threshold"]:
            self.violations["battery"] += 1
        for field in ["object_dx", "object_dy", "claw_alignment"]:
            if field not in sensors:
                self.violations["missing_fields"] += 1
                break

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        assert self.violations is not None
        return dict(self.violations)


def evaluation_suite_from_profile(profile: dict[str, Any]) -> EvaluationSuite:
    evaluation_cfg = profile.get("evaluation", {})
    task_spec = evaluation_cfg.get("task", "tabletop_grasp")
    if isinstance(task_spec, dict) and task_spec.get("type") == "custom_plugin":
        task = instantiate_plugin(task_spec.get("plugin", {}), profile=profile, config=task_spec)
    else:
        task_name = task_spec.get("name", "tabletop_grasp") if isinstance(task_spec, dict) else task_spec
        task = _task_registry(profile)[task_name]
    metric_specs = evaluation_cfg.get("metrics", ["task_performance", "boundary_violations"])
    metrics: list[EvaluationMetric] = []
    for metric_spec in metric_specs:
        if isinstance(metric_spec, dict) and metric_spec.get("type") == "custom_plugin":
            metrics.append(instantiate_plugin(metric_spec.get("plugin", {}), profile=profile, config=metric_spec))
        elif metric_spec == "task_performance":
            metrics.append(TaskPerformanceMetric())
        elif metric_spec == "boundary_violations":
            metrics.append(BoundaryViolationMetric(profile=profile))
        else:
            raise ValueError(f"Unsupported evaluation metric: {metric_spec}")
    return EvaluationSuite(task=task, metrics=metrics)


def describe_available_evaluations() -> dict[str, Any]:
    return {
        "tasks": {
            "tabletop_grasp": {
                "description": "Approach, align, and grasp a tabletop object.",
                "success_signal": "object_grasped > 0.5",
                "required_observation_fields": ["object_dx", "object_dy", "claw_alignment", "arm_extension", "arm_height"],
            },
            "hardware_link_validation": {
                "description": "Validate command/telemetry exchange and safety thresholds on hardware or mock transport.",
                "success_signal": "connection_alive > 0.5 and no safety stop",
                "required_observation_fields": ["connection_alive", "battery_level", "collision_risk"],
            },
        },
        "metrics": {
            "task_performance": "Tracks approach, alignment, grasp, visibility, energy, and success efficiency.",
            "boundary_violations": "Counts collision, battery, and required-observation boundary violations.",
            "custom_plugin": {
                "description": "Loads a user-defined evaluation metric from a Python module or file.",
                "config": {"plugin": describe_plugin_spec({})},
            },
        },
    }


def _task_registry(profile: dict[str, Any]) -> dict[str, EvaluationTaskDefinition]:
    boundaries = compute_boundary_conditions(profile)
    common_interface = {
        "camera_roles": ["dash", "claw"],
        "action_channels": ["chassis_forward", "chassis_turn", "arm_extend", "arm_lift", "gripper_close"],
    }
    return {
        "tabletop_grasp": EvaluationTaskDefinition(
            name="tabletop_grasp",
            description="Approach, align, and grasp a tabletop object with dash/claw perception.",
            success_signal="object_grasped > 0.5",
            required_observation_fields=["object_dx", "object_dy", "claw_alignment", "arm_extension", "arm_height"],
            boundary_conditions=boundaries,
            interface_requirements=common_interface,
        ),
        "hardware_link_validation": EvaluationTaskDefinition(
            name="hardware_link_validation",
            description="Validate protocol, observation freshness, battery margin, and safety stops.",
            success_signal="connection_alive > 0.5 and no safety_stop",
            required_observation_fields=["connection_alive", "battery_level", "collision_risk"],
            boundary_conditions=boundaries,
            interface_requirements=common_interface,
        ),
    }
