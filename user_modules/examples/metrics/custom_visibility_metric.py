from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, StepResult


@dataclass(slots=True)
class CustomVisibilityMetric:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    name: str = "custom_visibility"
    total_visibility: float = 0.0
    steps: int = 0

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        self.steps += 1
        self.total_visibility += sum(camera.features.get("target_visibility", 0.0) for camera in step_result.observation.cameras)

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        average = self.total_visibility / self.steps if self.steps else 0.0
        return {"average_visibility_sum": average, "steps": self.steps}
