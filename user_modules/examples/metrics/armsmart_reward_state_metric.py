from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.interfaces import ActionCommand, StepResult


@dataclass(slots=True)
class ARMSmartRewardStateMetric:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    name: str = "armsmart_reward_state"
    phase_counts: dict[str, int] = field(default_factory=dict)
    reward_component_sums: dict[str, float] = field(default_factory=dict)
    final_extension_sum: float = 0.0
    steps: int = 0

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        self.steps += 1
        phase = str(action.auxiliary.get("policy_phase", "unknown"))
        self.phase_counts[phase] = self.phase_counts.get(phase, 0) + 1
        for name, value in step_result.reward.components.items():
            self.reward_component_sums[name] = self.reward_component_sums.get(name, 0.0) + float(value)
        self.final_extension_sum += float(step_result.observation.sensors.get("arm_extension", 0.0))

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        average_extension = self.final_extension_sum / self.steps if self.steps else 0.0
        return {
            "phase_counts": dict(self.phase_counts),
            "reward_component_sums": dict(self.reward_component_sums),
            "average_arm_extension": average_extension,
            "steps": self.steps,
        }
