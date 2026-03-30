from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, StepResult


@dataclass(slots=True)
class EvaluationTaskDefinition:
    name: str
    description: str
    success_signal: str
    required_observation_fields: list[str]
    boundary_conditions: dict[str, Any]
    interface_requirements: dict[str, Any]


class EvaluationMetric(ABC):
    name: str

    @abstractmethod
    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(slots=True)
class EvaluationSuite:
    task: EvaluationTaskDefinition
    metrics: list[EvaluationMetric]

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        for metric in self.metrics:
            metric.update(action, step_result)

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        return {
            "task": {
                "name": self.task.name,
                "description": self.task.description,
                "success_signal": self.task.success_signal,
                "required_observation_fields": self.task.required_observation_fields,
                "boundary_conditions": self.task.boundary_conditions,
                "interface_requirements": self.task.interface_requirements,
            },
            "metrics": {
                metric.name: metric.summary(episodes=episodes, successes=successes, reward_total=reward_total)
                for metric in self.metrics
            },
        }
