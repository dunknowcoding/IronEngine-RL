from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ARMSmartRewardBlendUpdate:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    reward_gain: float = 0.14
    alignment_gain: float = 0.08
    grasp_gain: float = 0.1
    safety_penalty: float = 0.18
    name: str = "armsmart_reward_blend"

    def __post_init__(self) -> None:
        cfg = self.config or {}
        self.reward_gain = float(cfg.get("reward_gain", self.reward_gain))
        self.alignment_gain = float(cfg.get("alignment_gain", self.alignment_gain))
        self.grasp_gain = float(cfg.get("grasp_gain", self.grasp_gain))
        self.safety_penalty = float(cfg.get("safety_penalty", self.safety_penalty))

    def apply(self, weights: dict[str, float], observation_features: dict[str, float], repository_context: dict[str, Any]) -> dict[str, float]:
        adjusted = dict(weights)
        reward_summary = repository_context.get("recent_reward_summary", {})
        state_summary = repository_context.get("state_summary", {})
        success_rate = float(repository_context.get("success_rate", 0.0))
        alignment = float(observation_features.get("claw_alignment", 0.0))
        progress_reward = float(reward_summary.get("progress", observation_features.get("distance_progress", 0.0)))
        safety_cost = float(reward_summary.get("safety", observation_features.get("collision_risk", 0.0)))
        grasp_confidence = float(state_summary.get("grasp_confidence", observation_features.get("grasp_confidence", 0.0)))

        adjusted["claw_alignment"] = adjusted.get("claw_alignment", 0.0) + self.alignment_gain * alignment
        adjusted["visibility"] = adjusted.get("visibility", 0.0) + 0.5 * self.alignment_gain * float(observation_features.get("visibility", 0.0))
        adjusted["pregrasp_ready"] = adjusted.get("pregrasp_ready", 0.0) + self.grasp_gain * max(progress_reward, grasp_confidence)
        adjusted["object_distance"] = adjusted.get("object_distance", 0.0) - self.reward_gain * progress_reward
        adjusted["collision_risk"] = adjusted.get("collision_risk", 0.0) - self.safety_penalty * max(safety_cost, 1.0 - success_rate)
        adjusted["battery_level"] = adjusted.get("battery_level", 0.0) + 0.04 * float(repository_context.get("battery_margin", 0.0))
        return adjusted
