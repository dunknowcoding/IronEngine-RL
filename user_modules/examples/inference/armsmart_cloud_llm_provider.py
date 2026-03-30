from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.inference.llm_context import build_role_and_task_preamble
from ironengine_rl.interfaces import InferenceResult, Observation
from ironengine_rl.model_providers.rule_based import RuleBasedModelProvider


@dataclass(slots=True)
class ARMSmartCloudLLMProvider:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    fallback: RuleBasedModelProvider = field(default_factory=RuleBasedModelProvider)

    def infer(self, observation: Observation, repository_context: dict[str, Any]) -> InferenceResult:
        fallback = self.fallback.infer(observation, repository_context)
        prompt, metadata = self._build_prompt(observation, repository_context)
        notes = list(fallback.notes)
        notes.extend(
            [
                "Cloud LLM ARMSmart provider active.",
                f"Configured model: {(self.config or {}).get('model', 'unspecified')}",
                f"API key env: {(self.config or {}).get('api_key_env', 'unset')}",
                f"Role contract: {metadata.get('role_contract_file', 'SOUL.md')}",
                f"Resolved task: {metadata.get('task_name', 'framework_task')}",
                f"Task goal: {metadata.get('task_goal', 'unspecified')}",
                f"Prompt preview length: {len(prompt)} characters",
            ]
        )
        return InferenceResult(
            task_phase=fallback.task_phase,
            state_estimate={**fallback.state_estimate, "llm_prompt_chars": float(len(prompt)), "remote_reasoning": 1.0},
            reward_hints=dict(fallback.reward_hints),
            anomalies=list(fallback.anomalies),
            visual_summary=dict(fallback.visual_summary),
            notes=notes,
        )

    def _build_prompt(self, observation: Observation, repository_context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        cfg = self.config or {}
        role_and_task, metadata = build_role_and_task_preamble(self.profile or {}, cfg, repository_context)
        return (
            f"{role_and_task}\n"
            f"System prompt override: {cfg.get('system_prompt', 'You are the cloud ARMSmart planner.')}\n"
            f"Task: {cfg.get('task_name', 'armsmart_pick_place_real_task')}\n"
            f"Action scheme: {repository_context.get('action_scheme', {})}\n"
            f"Knowledge repository: {repository_context.get('knowledge_repository', {})}\n"
            f"Repository notes: {repository_context.get('repository_notes', [])}\n"
            f"Success rate: {repository_context.get('success_rate', 0.0)}\n"
            f"Recent rewards: {repository_context.get('recent_reward_summary', {})}\n"
            f"State summary: {repository_context.get('state_summary', {})}\n"
            f"Sensors: {observation.sensors}\n"
            f"Vision: {[camera.features for camera in observation.cameras]}"
        ), metadata
