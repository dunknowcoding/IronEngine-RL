from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.inference.llm_context import build_role_and_task_preamble
from ironengine_rl.inference.ollama_client import apply_ollama_decision, request_ollama_decision
from ironengine_rl.interfaces import InferenceResult, ModelProviderPort, Observation
from ironengine_rl.model_providers.rule_based import RuleBasedModelProvider


@dataclass(slots=True)
class PromptDrivenProvider(ModelProviderPort):
    backend_name: str
    provider_cfg: dict[str, Any]
    profile: dict[str, Any] = field(default_factory=dict)
    fallback_provider: RuleBasedModelProvider = field(default_factory=RuleBasedModelProvider)
    last_prompt_metadata: dict[str, Any] = field(default_factory=dict, init=False)

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        prompt = self.build_prompt(observation, context)
        fallback = self.fallback_provider.infer(observation, context)
        decision = request_ollama_decision(prompt=prompt, provider_cfg=self.provider_cfg, fallback=fallback)
        resolved = apply_ollama_decision(fallback, decision)
        return InferenceResult(
            task_phase=resolved.task_phase,
            state_estimate=dict(resolved.state_estimate),
            reward_hints=dict(resolved.reward_hints),
            anomalies=list(resolved.anomalies),
            visual_summary=dict(resolved.visual_summary),
            notes=list(resolved.notes)
            + [
                f"Prompt-driven provider active: {self.backend_name}",
                f"Prompt template: {self.provider_cfg.get('prompt_template', 'default_grasp_controller')}",
                f"Configured model: {self.provider_cfg.get('model', 'unspecified')}",
                f"Role contract: {self.last_prompt_metadata.get('role_contract_file', 'SOUL.md')}",
                f"Resolved task: {self.last_prompt_metadata.get('task_name', 'framework_task')}",
                f"Task goal: {self.last_prompt_metadata.get('task_goal', 'unspecified')}",
                f"Prompt preview length: {len(prompt)} characters",
            ],
        )

    def build_prompt(self, observation: Observation, context: dict[str, Any]) -> str:
        role_and_task, metadata = build_role_and_task_preamble(self.profile, self.provider_cfg, context)
        self.last_prompt_metadata = metadata
        template = self.provider_cfg.get(
            "system_prompt",
            "You are IronEngine-RL. Use the observation, repository context, and safety limits to choose the next grasping phase.",
        )
        return (
            f"{role_and_task}\n"
            f"System prompt override: {template}\n"
            f"Action scheme: {context.get('action_scheme', self.profile.get('action_scheme', {}))}\n"
            f"Observation sensors: {observation.sensors}\n"
            f"Visual summary: {[camera.features for camera in observation.cameras]}\n"
            f"Repository notes: {context.get('repository_notes', [])}\n"
            f"Success rate: {context.get('success_rate', 0.0)}"
        )


class OllamaPromptProvider(PromptDrivenProvider):
    def __init__(self, profile: dict[str, Any], provider_cfg: dict[str, Any]) -> None:
        super().__init__(backend_name="ollama_prompt", provider_cfg=provider_cfg, profile=profile)


class LMStudioPromptProvider(PromptDrivenProvider):
    def __init__(self, profile: dict[str, Any], provider_cfg: dict[str, Any]) -> None:
        super().__init__(backend_name="lmstudio_prompt", provider_cfg=provider_cfg, profile=profile)


class CloudPromptProvider(PromptDrivenProvider):
    def __init__(self, profile: dict[str, Any], provider_cfg: dict[str, Any]) -> None:
        super().__init__(backend_name="cloud_prompt", provider_cfg=provider_cfg, profile=profile)
