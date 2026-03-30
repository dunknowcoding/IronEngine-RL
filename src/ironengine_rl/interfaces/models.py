from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_ACTION_CHANNELS = [
    "chassis_forward",
    "chassis_strafe",
    "chassis_turn",
    "arm_lift",
    "arm_extend",
    "wrist_yaw",
    "gripper_close",
]


@dataclass(slots=True)
class ActionScheme:
    name: str = "direct_channel_control"
    command_channels: list[str] = field(default_factory=lambda: list(DEFAULT_ACTION_CHANNELS))
    feedback_fields: list[str] = field(default_factory=list)
    result_fields: list[str] = field(default_factory=lambda: ["reward.total", "reward.components", "done", "info"])
    schedule_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CameraFrame:
    camera_id: str
    role: str
    timestamp_s: float
    features: dict[str, float]
    detections: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class Observation:
    timestamp_s: float
    sensors: dict[str, float]
    cameras: list[CameraFrame]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def feedback(self) -> dict[str, float]:
        return self.sensors

    @feedback.setter
    def feedback(self, value: dict[str, float]) -> None:
        self.sensors = value


@dataclass(slots=True)
class InferenceResult:
    task_phase: str
    state_estimate: dict[str, float]
    reward_hints: dict[str, float]
    anomalies: list[str] = field(default_factory=list)
    visual_summary: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def results(self) -> dict[str, Any]:
        return {
            "task_phase": self.task_phase,
            "state_estimate": self.state_estimate,
            "reward_hints": self.reward_hints,
            "anomalies": self.anomalies,
            "visual_summary": self.visual_summary,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ActionCommand:
    chassis_forward: float = 0.0
    chassis_strafe: float = 0.0
    chassis_turn: float = 0.0
    arm_lift: float = 0.0
    arm_extend: float = 0.0
    wrist_yaw: float = 0.0
    gripper_close: float = 0.0
    auxiliary: dict[str, Any] = field(default_factory=dict)

    @property
    def action_scheme(self) -> str:
        return str(self.auxiliary.get("action_scheme", "direct_channel_control"))

    @action_scheme.setter
    def action_scheme(self, value: str) -> None:
        self.auxiliary["action_scheme"] = value

    @property
    def command(self) -> dict[str, Any]:
        return {
            "chassis_forward": self.chassis_forward,
            "chassis_strafe": self.chassis_strafe,
            "chassis_turn": self.chassis_turn,
            "arm_lift": self.arm_lift,
            "arm_extend": self.arm_extend,
            "wrist_yaw": self.wrist_yaw,
            "gripper_close": self.gripper_close,
            "auxiliary": dict(self.auxiliary),
            "action_scheme": self.action_scheme,
        }


@dataclass(slots=True)
class RewardBreakdown:
    total: float
    components: dict[str, float]


@dataclass(slots=True)
class StepResult:
    observation: Observation
    reward: RewardBreakdown
    done: bool
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def results(self) -> dict[str, Any]:
        return {
            "feedback": self.observation.feedback,
            "reward_total": self.reward.total,
            "reward_components": self.reward.components,
            "done": self.done,
            "info": self.info,
        }
