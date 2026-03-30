from __future__ import annotations

from dataclasses import dataclass

from ironengine_rl.interfaces import InferenceResult, ModelProviderPort, Observation


@dataclass(slots=True)
class InferenceEngine:
    model_provider: ModelProviderPort

    def infer(self, observation: Observation, repository_context: dict[str, object]) -> InferenceResult:
        return self.model_provider.infer(observation, repository_context)
