from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from ironengine_rl.config import load_profile
from ironengine_rl.framework.factories import build_runtime_components
from ironengine_rl.interfaces import CameraFrame, Observation, RewardBreakdown, StepResult
from user_modules.examples.inference.armsmart_adaptive_torch_provider import ARMSmartPolicyNet

try:
    import torch
except Exception:
    torch = None


def ensure_demo_weights(profile: dict[str, Any]) -> Path | None:
    if torch is None:
        return None
    weights_value = str(profile.get("model_provider", {}).get("weights_file", "") or "")
    if not weights_value:
        return None
    weights_path = Path(weights_value)
    if not weights_path.is_absolute():
        weights_path = REPO_ROOT / weights_path
    if weights_path.exists():
        return weights_path
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(7)
    model = ARMSmartPolicyNet()
    torch.save(model.state_dict(), weights_path)
    return weights_path


def build_observation(timestamp_s: float, *, object_dx: float, object_dy: float, claw_alignment: float, arm_extension: float, arm_height: float, gripper_close: float, object_grasped: float, battery_level: float = 0.92, collision_risk: float = 0.05, dash_visibility: float = 0.85, claw_visibility: float = 0.8) -> Observation:
    return Observation(
        timestamp_s=timestamp_s,
        sensors={
            "connection_alive": 1.0,
            "battery_level": battery_level,
            "collision_risk": collision_risk,
            "object_dx": object_dx,
            "object_dy": object_dy,
            "claw_alignment": claw_alignment,
            "arm_extension": arm_extension,
            "arm_height": arm_height,
            "gripper_close": gripper_close,
            "object_grasped": object_grasped,
        },
        cameras=[
            CameraFrame(
                camera_id="dash",
                role="dash",
                timestamp_s=timestamp_s,
                features={"target_visibility": dash_visibility},
                detections=[{"label": "target_block", "confidence": 0.93, "is_target": True}],
            ),
            CameraFrame(
                camera_id="claw",
                role="claw",
                timestamp_s=timestamp_s,
                features={"target_visibility": claw_visibility},
                detections=[{"label": "target_block", "confidence": 0.9, "is_target": True}],
            ),
        ],
        metadata={"target_object_label": "target_block", "trial": "pytorch_grasp_process"},
    )


def make_trial_steps() -> list[dict[str, Any]]:
    return [
        {
            "label": "approach",
            "observation": build_observation(0.1, object_dx=0.58, object_dy=0.06, claw_alignment=0.42, arm_extension=0.18, arm_height=0.16, gripper_close=0.05, object_grasped=0.0, dash_visibility=0.76, claw_visibility=0.7),
            "reward": RewardBreakdown(total=0.8, components={"progress": 0.55, "alignment": 0.12, "safety": 0.05}),
            "done": False,
            "success": False,
        },
        {
            "label": "pregrasp",
            "observation": build_observation(0.2, object_dx=0.24, object_dy=0.02, claw_alignment=0.81, arm_extension=0.46, arm_height=0.24, gripper_close=0.18, object_grasped=0.0, dash_visibility=0.9, claw_visibility=0.84),
            "reward": RewardBreakdown(total=1.7, components={"progress": 1.05, "alignment": 0.42, "safety": 0.04}),
            "done": False,
            "success": False,
        },
        {
            "label": "grasp",
            "observation": build_observation(0.3, object_dx=0.08, object_dy=0.0, claw_alignment=0.95, arm_extension=0.63, arm_height=0.31, gripper_close=0.78, object_grasped=1.0, dash_visibility=0.94, claw_visibility=0.92),
            "reward": RewardBreakdown(total=3.4, components={"progress": 1.6, "alignment": 0.8, "safety": 0.02, "success": 0.98}),
            "done": True,
            "success": True,
        },
    ]


def main() -> None:
    profile_path = REPO_ROOT / "examples" / "inference" / "armsmart_pytorch_complete" / "profile.json"
    profile = load_profile(profile_path)
    weights_path = ensure_demo_weights(profile)

    run_dir = REPO_ROOT / "logs" / "examples" / "inference" / "armsmart_pytorch_complete" / f"grasp_trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    components = build_runtime_components(profile, run_dir=run_dir)
    provider = components.provider
    agent = components.agent
    safety = components.safety
    repository = components.repository

    safety.reset()
    steps_payload: list[dict[str, Any]] = []
    for index, step in enumerate(make_trial_steps(), start=1):
        observation = step["observation"]
        context = repository.build_context()
        context["database"] = {"enabled": True}
        context["action_scheme"] = profile["action_scheme"]
        inference = provider.infer(observation, context)
        action = agent.act(observation, inference, context)
        safe_action = safety.apply(action, observation, inference)
        step_result = StepResult(
            observation=observation,
            reward=step["reward"],
            done=bool(step["done"]),
            info={"success": bool(step["success"]), "step_label": step["label"], "step_index": index},
        )
        repository.record_transition(observation, inference, safe_action, step_result)
        steps_payload.append(
            {
                "step": index,
                "label": step["label"],
                "inference_phase": inference.task_phase,
                "policy_phase": safe_action.auxiliary.get("policy_phase", "unknown"),
                "action_scheme": safe_action.action_scheme,
                "policy_score": inference.state_estimate.get("policy_score"),
                "grasp_confidence": inference.state_estimate.get("grasp_confidence"),
                "adaptive_pregrasp_weight": inference.state_estimate.get("adaptive_pregrasp_weight"),
                "adaptive_distance_weight": inference.state_estimate.get("adaptive_distance_weight"),
                "adaptive_collision_weight": inference.state_estimate.get("adaptive_collision_weight"),
                "anomalies": list(inference.anomalies),
                "notes": list(inference.notes),
                "command": safe_action.command,
                "reward_components": dict(step["reward"].components),
            }
        )

    summary_path = repository.write_summary()
    report_path = run_dir / "grasp_trial_report.json"
    database_path = run_dir / str(profile.get("repository", {}).get("database_file", "armsmart_experiment_db.json"))
    payload = {
        "profile": str(profile_path.relative_to(REPO_ROOT)),
        "weights_path": str(weights_path) if weights_path is not None else None,
        "summary_path": str(summary_path),
        "database_path": str(database_path),
        "steps": steps_payload,
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
