from __future__ import annotations

from typing import Any

from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation, StepResult
from user_modules.examples.repositories.persistent_json_repository import PersistentJsonRepository


class ARMSmartExperimentRepository(PersistentJsonRepository):
    def __init__(self, profile: dict[str, Any], run_dir, config: dict[str, Any] | None = None) -> None:
        super().__init__(profile=profile, run_dir=run_dir, config=config)
        self._recent_reward_summary: dict[str, float] = {}
        self._state_summary: dict[str, float] = {}

    def build_context(self) -> dict[str, Any]:
        context = super().build_context()
        context["recent_reward_summary"] = dict(self._recent_reward_summary)
        context["state_summary"] = dict(self._state_summary)
        context["battery_margin"] = float(self._state_summary.get("battery_margin", 0.0))
        return context

    def record_transition(
        self,
        observation: Observation,
        inference: InferenceResult,
        action: ActionCommand,
        step_result: StepResult,
    ) -> None:
        super().record_transition(observation, inference, action, step_result)
        self._recent_reward_summary = {name: float(value) for name, value in step_result.reward.components.items()}
        self._state_summary = {
            "grasp_confidence": float(inference.state_estimate.get("grasp_confidence", inference.state_estimate.get("policy_score", 0.0))),
            "object_distance": float(inference.state_estimate.get("object_distance", 0.0)),
            "battery_margin": max(0.0, float(observation.sensors.get("battery_level", 1.0)) - float(self.profile.get("safety", {}).get("low_battery_stop_threshold", 0.15))),
            "arm_extension": float(observation.sensors.get("arm_extension", 0.0)),
        }
        self._database.setdefault("state_trace", []).append(dict(self._state_summary))
        self._database.setdefault("reward_trace", []).append(dict(self._recent_reward_summary))
        self._database.setdefault("policy_trace", []).append({
            "phase": action.auxiliary.get("policy_phase", "unknown"),
            "action_scheme": action.action_scheme,
        })
        self._flush_database()
