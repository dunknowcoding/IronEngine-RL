
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import ActionCommand, InferenceResult, Observation, StepResult


class EnvironmentPort(ABC):
    @abstractmethod
    def reset(self) -> Observation:
        raise NotImplementedError

    @abstractmethod
    def step(self, action: ActionCommand) -> StepResult:
        raise NotImplementedError


class AgentPort(ABC):
    @abstractmethod
    def act(self, observation: Observation, inference: InferenceResult, repository_context: dict[str, Any]) -> ActionCommand:
        raise NotImplementedError


class SafetyPolicyPort(ABC):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply(self, action: ActionCommand, observation: Observation, inference: InferenceResult) -> ActionCommand:
        raise NotImplementedError


class ModelProviderPort(ABC):
    @abstractmethod
    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        raise NotImplementedError


class CameraProviderPort(ABC):
    @abstractmethod
    def capture(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class TransportPort(ABC):
    @abstractmethod
    def send(self, command: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def receive(self) -> dict[str, Any]:
        raise NotImplementedError


class KnowledgeRepositoryPort(ABC):
    @abstractmethod
    def build_context(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def record_transition(
        self,
        observation: Observation,
        inference: InferenceResult,
        action: ActionCommand,
        step_result: StepResult,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply_update_instructions(self, instructions: dict[str, Any]) -> None:
        raise NotImplementedError


class UpdateStrategyPort(ABC):
    @abstractmethod
    def apply(self, weights: dict[str, float], observation_features: dict[str, float], repository_context: dict[str, Any]) -> dict[str, float]:
        raise NotImplementedError


class PlatformPort(ABC):
    @abstractmethod
    def build_environment(self, profile: dict[str, Any]) -> EnvironmentPort:
        raise NotImplementedError

    @abstractmethod
    def build_manifest(self, profile: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
