from __future__ import annotations

from typing import Any

from ironengine_rl.interfaces import InferenceResult, ModelProviderPort, Observation
from ironengine_rl.model_providers.linear_policy import LinearPolicyProvider
from ironengine_rl.training import update_strategy_from_config


class PyTorchTrainableProvider(ModelProviderPort):
    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        self.provider_cfg = profile.get("model_provider", {})
        self.linear_fallback = LinearPolicyProvider(profile)
        self.update_strategy = update_strategy_from_config(self.provider_cfg.get("update_strategy"))
        self.torch_available = self._detect_torch()

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        base_result = self.linear_fallback.infer(observation, context)
        base_features = {
            "object_distance": float(base_result.state_estimate.get("object_distance", 0.0)),
            "claw_alignment": float(observation.sensors.get("claw_alignment", 0.0)),
            "pregrasp_ready": float(observation.sensors.get("pregrasp_ready", 0.0)),
            "visibility": sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras) / max(len(observation.cameras), 1),
        }
        adjusted_weights = self.update_strategy.apply(dict(self.linear_fallback.weights), base_features, context)
        policy_score = sum(adjusted_weights.get(name, 0.0) * value for name, value in {"object_distance": base_features["object_distance"], "claw_alignment": base_features["claw_alignment"], "pregrasp_ready": base_features["pregrasp_ready"], "visibility": base_features["visibility"], "bias": 1.0}.items())
        grasp_ready = 1.0 if policy_score >= float(self.provider_cfg.get("grasp_threshold", 0.35)) else 0.0
        notes = list(base_result.notes)
        notes.append("PyTorch-trainable provider scaffold active.")
        notes.append("Torch available." if self.torch_available else "Torch not installed; using framework linear fallback.")
        update_strategy = self.provider_cfg.get("update_strategy", {}).get("type", "none")
        notes.append(f"Update strategy: {update_strategy}")
        return InferenceResult(
            task_phase="grasp" if grasp_ready else "approach",
            state_estimate={**base_result.state_estimate, "grasp_ready": grasp_ready, "policy_score": policy_score},
            reward_hints=dict(base_result.reward_hints),
            anomalies=list(base_result.anomalies),
            visual_summary=dict(base_result.visual_summary),
            notes=notes,
        )

    @staticmethod
    def _detect_torch() -> bool:
        try:
            import torch  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True
