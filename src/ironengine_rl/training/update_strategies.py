from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ironengine_rl.plugins import describe_plugin_spec, instantiate_plugin


class UpdateStrategy(ABC):
    name: str

    @abstractmethod
    def apply(self, weights: dict[str, float], observation_features: dict[str, float], repository_context: dict[str, Any]) -> dict[str, float]:
        raise NotImplementedError


@dataclass(slots=True)
class NoOpUpdateStrategy(UpdateStrategy):
    name: str = "none"

    def apply(self, weights: dict[str, float], observation_features: dict[str, float], repository_context: dict[str, Any]) -> dict[str, float]:
        return dict(weights)


@dataclass(slots=True)
class RepositoryLinearBlendUpdate(UpdateStrategy):
    blend_factor: float = 0.12
    success_gain: float = 0.08
    name: str = "repository_linear_blend"

    def apply(self, weights: dict[str, float], observation_features: dict[str, float], repository_context: dict[str, Any]) -> dict[str, float]:
        adjusted = dict(weights)
        success_rate = float(repository_context.get("success_rate", 0.0))
        alignment = float(observation_features.get("claw_alignment", 0.0))
        adjusted["pregrasp_ready"] = adjusted.get("pregrasp_ready", 0.0) + self.blend_factor * (1.0 - success_rate)
        adjusted["visibility"] = adjusted.get("visibility", 0.0) + self.blend_factor * alignment
        adjusted["object_distance"] = adjusted.get("object_distance", 0.0) - self.success_gain * success_rate
        return adjusted


def update_strategy_from_config(config: dict[str, Any] | None) -> UpdateStrategy:
    config = config or {}
    strategy_type = config.get("type", "none")
    if strategy_type == "custom_plugin":
        return instantiate_plugin(config.get("plugin", {}), config=config)
    if strategy_type == "none":
        return NoOpUpdateStrategy()
    if strategy_type == "repository_linear_blend":
        return RepositoryLinearBlendUpdate(
            blend_factor=float(config.get("blend_factor", 0.12)),
            success_gain=float(config.get("success_gain", 0.08)),
        )
    raise ValueError(f"Unsupported update strategy: {strategy_type}")


def describe_available_update_strategies() -> dict[str, Any]:
    return {
        "none": {
            "description": "Leaves framework weights unchanged; useful for fixed baselines.",
            "config": {},
        },
        "repository_linear_blend": {
            "description": "Fine-tunes shared weights using repository success-rate and alignment signals.",
            "config": {
                "blend_factor": "float",
                "success_gain": "float",
            },
        },
        "custom_plugin": {
            "description": "Loads a user-defined update strategy from a Python module or file.",
            "config": {
                "plugin": describe_plugin_spec({}),
            },
        },
    }
