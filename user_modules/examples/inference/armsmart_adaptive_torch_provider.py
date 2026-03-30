from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ironengine_rl.interfaces import InferenceResult, Observation
from ironengine_rl.plugins import instantiate_plugin

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None


FEATURE_NAMES = [
    "object_dx",
    "object_dy",
    "claw_alignment",
    "arm_extension",
    "arm_height",
    "battery_level",
    "collision_risk",
    "visibility",
    "connection_alive",
]


if nn is not None:
    class ARMSmartPolicyNet(nn.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(len(FEATURE_NAMES), 24),
                nn.ReLU(),
                nn.Linear(24, 12),
                nn.ReLU(),
                nn.Linear(12, 3),
            )

        def forward(self, inputs):  # type: ignore[override]
            return self.network(inputs)
else:
    class ARMSmartPolicyNet:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise RuntimeError("ARMSmartPolicyNet requires torch to be installed.")


@dataclass(slots=True)
class ARMSmartAdaptiveTorchProvider:
    profile: dict[str, Any]
    config: dict[str, Any] | None = None
    model: Any = field(default=None, init=False)
    torch_available: bool = field(default=False, init=False)
    weights_loaded: bool = field(default=False, init=False)
    weights_path: str = field(default="", init=False)
    update_strategy: Any = field(default=None, init=False)
    update_strategy_name: str = field(default="none", init=False)
    grasp_threshold: float = field(default=0.58, init=False)

    def __post_init__(self) -> None:
        provider_cfg = self.config or self.profile.get("model_provider", {})
        self.torch_available = torch is not None and nn is not None
        self.grasp_threshold = float(provider_cfg.get("grasp_threshold", self.grasp_threshold))
        self.update_strategy_name = str(provider_cfg.get("update_strategy", {}).get("type", "none"))
        if self.update_strategy_name == "custom_plugin":
            self.update_strategy = instantiate_plugin(provider_cfg.get("update_strategy", {}).get("plugin", {}), profile=self.profile, config=provider_cfg.get("update_strategy", {}))
        else:
            from ironengine_rl.training import update_strategy_from_config

            self.update_strategy = update_strategy_from_config(provider_cfg.get("update_strategy", {}))
        if self.torch_available:
            self.model = ARMSmartPolicyNet()
            weights_file = str(provider_cfg.get("weights_file", "") or "")
            resolved_weights = self._resolve_weights_path(weights_file)
            self.weights_path = str(resolved_weights) if resolved_weights is not None else ""
            if resolved_weights is not None and resolved_weights.exists():
                state_dict = torch.load(resolved_weights, map_location="cpu")
                self.model.load_state_dict(state_dict)
                self.weights_loaded = True
            self.model.eval()

    def infer(self, observation: Observation, repository_context: dict[str, Any]) -> InferenceResult:
        feature_map = build_feature_map(observation)
        adaptive_weights = self.update_strategy.apply(_base_weights(), feature_map, repository_context)
        policy_logits = self._policy_logits(feature_map, adaptive_weights)
        policy_score = max(policy_logits)
        grasp_confidence = float(policy_logits[2])
        lift_readiness = float(policy_logits[1])
        object_grasped = float(observation.sensors.get("object_grasped", 0.0))
        if object_grasped > 0.5:
            grasp_confidence = max(grasp_confidence, 0.92)
            lift_readiness = max(lift_readiness, 0.75)
        object_distance = (feature_map["object_dx"] ** 2 + feature_map["object_dy"] ** 2) ** 0.5
        heading_error_deg = feature_map["object_dy"] * 45.0
        task_phase = "approach"
        if grasp_confidence > self.grasp_threshold:
            task_phase = "grasp"
        elif lift_readiness > 0.5:
            task_phase = "pregrasp"
        reward_hints = {
            "distance_progress": max(0.0, 1.0 - object_distance),
            "alignment_bonus": feature_map["claw_alignment"],
            "visibility_bonus": feature_map["visibility"],
            "grasp_bonus": grasp_confidence,
            "safety": feature_map["collision_risk"],
        }
        notes = [
            "Adaptive ARMSmart PyTorch provider active.",
            "Torch available." if self.torch_available else "Torch not installed; using analytic policy fallback.",
            f"Weights loaded: {self.weights_loaded}",
            f"Weights path: {self.weights_path or 'not configured'}",
            f"Update strategy: {self.update_strategy_name}",
        ]
        if repository_context.get("database", {}).get("enabled"):
            notes.append("Persistent repository context available.")
        return InferenceResult(
            task_phase=task_phase,
            state_estimate={
                "object_distance": object_distance,
                "heading_error_deg": heading_error_deg,
                "grasp_confidence": grasp_confidence,
                "lift_readiness": lift_readiness,
                "policy_score": policy_score,
                "state_update_strength": float(repository_context.get("recent_reward_summary", {}).get("progress", 0.0)),
                "arm_extension": feature_map["arm_extension"],
                "arm_height": feature_map["arm_height"],
                "object_grasped": object_grasped,
                "adaptive_distance_weight": float(adaptive_weights.get("object_distance", 0.0)),
                "adaptive_alignment_weight": float(adaptive_weights.get("claw_alignment", 0.0)),
                "adaptive_pregrasp_weight": float(adaptive_weights.get("pregrasp_ready", 0.0)),
                "adaptive_collision_weight": float(adaptive_weights.get("collision_risk", 0.0)),
            },
            reward_hints=reward_hints,
            anomalies=["low_battery"] if feature_map["battery_level"] < 0.2 else [],
            visual_summary={"visibility": feature_map["visibility"]},
            notes=notes,
        )

    def _policy_logits(self, feature_map: dict[str, float], adaptive_weights: dict[str, float]) -> list[float]:
        adaptive_logits = _adaptive_logits(feature_map, adaptive_weights)
        if self.model is not None and self.torch_available:
            tensor = torch.tensor([[feature_map[name] for name in FEATURE_NAMES]], dtype=torch.float32)
            with torch.no_grad():
                logits = [float(value) for value in self.model(tensor)[0].tolist()]
            return [0.65 * logits[index] + 0.35 * adaptive_logits[index] for index in range(3)]
        return adaptive_logits

    def _resolve_weights_path(self, weights_file: str) -> Path | None:
        if not weights_file:
            return None
        candidate = Path(weights_file)
        if candidate.is_absolute():
            return candidate
        if candidate.exists():
            return candidate
        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / candidate


def _adaptive_logits(feature_map: dict[str, float], adaptive_weights: dict[str, float]) -> list[float]:
    approach = 0.65 - adaptive_weights.get("object_distance", 0.0) * feature_map["object_dx"]
    pregrasp = 0.4 + adaptive_weights.get("claw_alignment", 0.0) * feature_map["claw_alignment"] + 0.2 * feature_map["arm_extension"]
    grasp = 0.2 + adaptive_weights.get("pregrasp_ready", 0.0) * feature_map["claw_alignment"] + 0.3 * feature_map["visibility"] - 0.4 * feature_map["collision_risk"]
    return [approach, pregrasp, grasp]


def build_feature_map(observation: Observation) -> dict[str, float]:
    visibility = sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras) / max(len(observation.cameras), 1)
    sensors = observation.sensors
    return {
        "object_dx": float(sensors.get("object_dx", 0.0)),
        "object_dy": float(sensors.get("object_dy", 0.0)),
        "claw_alignment": float(sensors.get("claw_alignment", 0.0)),
        "arm_extension": float(sensors.get("arm_extension", 0.0)),
        "arm_height": float(sensors.get("arm_height", 0.0)),
        "battery_level": float(sensors.get("battery_level", 1.0)),
        "collision_risk": float(sensors.get("collision_risk", 0.0)),
        "visibility": float(visibility),
        "connection_alive": float(sensors.get("connection_alive", 1.0)),
    }


def _base_weights() -> dict[str, float]:
    return {
        "object_distance": -0.55,
        "claw_alignment": 0.85,
        "pregrasp_ready": 0.7,
        "visibility": 0.35,
        "collision_risk": -0.6,
        "battery_level": 0.08,
    }
