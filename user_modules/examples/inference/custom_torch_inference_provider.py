from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ironengine_rl.interfaces import InferenceResult, Observation

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
]


if nn is not None:
    class TinyGraspNet(nn.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(len(FEATURE_NAMES), 16),
                nn.ReLU(),
                nn.Linear(16, 8),
                nn.ReLU(),
                nn.Linear(8, 2),
            )

        def forward(self, inputs):  # type: ignore[override]
            return self.network(inputs)
else:
    class TinyGraspNet:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise RuntimeError("TinyGraspNet requires torch to be installed.")


@dataclass(slots=True)
class CustomTorchPolicyProvider:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    model: Any = field(default=None, init=False)
    torch_available: bool = field(default=False, init=False)
    weights_loaded: bool = field(default=False, init=False)
    weights_path: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        provider_cfg = self.config or self.profile.get("model_provider", {}) if self.profile else {}
        self.weights_path = str(provider_cfg.get("weights_file", provider_cfg.get("torch_weights_file", "")) or "")
        self.torch_available = torch is not None and nn is not None
        if not self.torch_available:
            return
        self.model = TinyGraspNet()
        if self.weights_path and Path(self.weights_path).exists():
            state_dict = torch.load(self.weights_path, map_location="cpu")
            self.model.load_state_dict(state_dict)
            self.weights_loaded = True
        self.model.eval()

    def infer(self, observation: Observation, context: dict[str, Any]) -> InferenceResult:
        feature_map = build_feature_map(observation)
        policy_score = self._policy_score(feature_map)
        grasp_ready = 1.0 if policy_score >= float((self.config or {}).get("grasp_threshold", 0.55)) else 0.0
        notes = [
            "Custom PyTorch inference provider active.",
            "Torch available." if self.torch_available else "Torch not installed; using heuristic fallback.",
            f"Weights loaded: {self.weights_loaded}",
        ]
        if self.weights_path:
            notes.append(f"Weights file: {self.weights_path}")
        return InferenceResult(
            task_phase="grasp" if grasp_ready > 0.5 else "approach",
            state_estimate={
                "object_distance": (feature_map["object_dx"] ** 2 + feature_map["object_dy"] ** 2) ** 0.5,
                "heading_error_deg": feature_map["object_dy"] * 45.0,
                "grasp_ready": grasp_ready,
                "policy_score": policy_score,
                "arm_extension": feature_map["arm_extension"],
                "arm_height": feature_map["arm_height"],
            },
            reward_hints={
                "distance_progress": max(0.0, 1.0 - abs(feature_map["object_dx"])),
                "alignment_bonus": feature_map["claw_alignment"],
                "visibility_bonus": feature_map["visibility"],
            },
            anomalies=["low_battery"] if feature_map["battery_level"] < 0.2 else [],
            visual_summary={"visibility": feature_map["visibility"]},
            notes=notes,
        )

    def _policy_score(self, feature_map: dict[str, float]) -> float:
        if self.model is not None and self.torch_available:
            tensor = torch.tensor([[feature_map[name] for name in FEATURE_NAMES]], dtype=torch.float32)
            with torch.no_grad():
                logits = self.model(tensor)
                probability = torch.softmax(logits, dim=-1)[0, 1].item()
            return float(probability)
        return heuristic_policy_score(feature_map)


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
    }


def heuristic_policy_score(feature_map: dict[str, float]) -> float:
    score = 0.5
    score += 0.35 * feature_map["claw_alignment"]
    score += 0.2 * feature_map["visibility"]
    score += 0.1 * feature_map["arm_extension"]
    score -= 0.4 * abs(feature_map["object_dx"])
    score -= 0.25 * feature_map["collision_risk"]
    score += 0.05 * feature_map["battery_level"]
    return max(0.0, min(1.0, score))
