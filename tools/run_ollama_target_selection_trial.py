from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl.config import load_profile
from ironengine_rl.framework import build_validation_report
from ironengine_rl.framework.factories import build_runtime_components

PREFERRED_MODELS = [
    "qwen3.5:2b",
    "qwen3.5:4b",
    "qwen3.5:0.8b",
    "llama3.2:3b",
    "llama3.2:1b",
    "gemma3:4b",
    "phi4-mini:3.8b",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local-Ollama target-selection grasp simulation.")
    parser.add_argument(
        "--profile",
        default="examples/inference/armsmart_ollama_target_selection/profile.json",
        help="Path to the simulation profile.",
    )
    parser.add_argument("--episodes", type=int, default=1, help="Number of episodes to run.")
    parser.add_argument("--steps", type=int, default=28, help="Maximum steps per episode.")
    parser.add_argument("--model", default="auto", help="Ollama model to use, or 'auto'.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    profile_path = (repo_root / args.profile).resolve()
    profile = load_profile(profile_path)
    selected_model = select_model(profile, args.model)
    profile["model_provider"]["model"] = selected_model
    validation = build_validation_report(profile)
    if not validation["schema"]["valid"] or not validation["compatibility"].get("compatible", False):
        print(json.dumps({"status": "invalid_profile", "validation": validation}, indent=2))
        raise SystemExit(1)

    run_root = repo_root / profile["logs"]["run_dir"] / datetime.now().strftime("%Y%m%d_%H%M%S")
    components = build_runtime_components(profile, run_dir=run_root)
    repository = components.repository
    episodes_payload: list[dict[str, Any]] = []
    boundary_stop_count = 0

    for episode_index in range(args.episodes):
        observation = components.environment.reset()
        components.safety.reset()
        repository.apply_update_instructions({"note": f"Target-selection episode {episode_index + 1} started with model {selected_model}"})
        steps_payload: list[dict[str, Any]] = []
        final_step: dict[str, Any] | None = None
        for step_index in range(args.steps):
            context = repository.build_context()
            inference = components.provider.infer(observation, context)
            action = components.agent.act(observation, inference, context)
            safe_action = components.safety.apply(action, observation, inference)
            step_result = components.environment.step(safe_action)
            repository.record_transition(observation, inference, safe_action, step_result)
            if safe_action.auxiliary.get("safety_stop"):
                boundary_stop_count += 1
            final_step = {
                "step": step_index + 1,
                "task_phase": inference.task_phase,
                "grasp_confidence": float(inference.state_estimate.get("grasp_confidence", 0.0)),
                "object_distance": float(step_result.observation.sensors.get("object_distance", 0.0)),
                "claw_alignment": float(step_result.observation.sensors.get("claw_alignment", 0.0)),
                "object_grasped": float(step_result.observation.sensors.get("object_grasped", 0.0)),
                "target_object_label": step_result.observation.metadata.get("target_object_label"),
                "dash_detections": next((camera.detections for camera in step_result.observation.cameras if camera.role == "dash"), []),
                "action": safe_action.command,
                "reward": step_result.reward.components,
                "notes": inference.notes[-6:],
                "done": step_result.done,
                "success": bool(step_result.info.get("success", False)),
            }
            steps_payload.append(final_step)
            observation = step_result.observation
            if step_result.done:
                break
        episodes_payload.append(
            {
                "episode": episode_index + 1,
                "success": bool(final_step and final_step["success"]),
                "final_step": final_step,
                "step_count": len(steps_payload),
                "trajectory": steps_payload,
            }
        )

    summary_path = repository.write_summary()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result = {
        "status": "completed",
        "selected_model": selected_model,
        "profile": str(profile_path),
        "summary_path": str(summary_path),
        "success": bool(summary.get("successes", 0) >= 1),
        "boundary_stop_count": boundary_stop_count,
        "soul_path": str((repo_root / profile["llm"]["role_contract_file"]).resolve()),
        "modules": {
            "provider": type(components.provider).__name__,
            "agent": type(components.agent).__name__,
            "safety": type(components.safety).__name__,
            "repository": type(components.repository).__name__,
        },
        "evaluation": summary.get("evaluation", {}),
        "task_metrics": summary.get("task_metrics", {}),
        "repository_notes": summary.get("repository_notes", []),
        "episodes": episodes_payload,
    }
    print(json.dumps(result, indent=2))


def select_model(profile: dict[str, Any], requested_model: str) -> str:
    if requested_model and requested_model != "auto":
        return requested_model
    available = list_models(profile["model_provider"].get("base_url", "http://127.0.0.1:11434"))
    for model in PREFERRED_MODELS:
        if model in available:
            return model
    configured = str(profile["model_provider"].get("model", "")).strip()
    if configured:
        return configured
    if available:
        return available[0]
    raise RuntimeError("No Ollama models are available.")


def list_models(base_url: str) -> list[str]:
    with urlopen(f"{str(base_url).rstrip('/')}/api/tags", timeout=5.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]


if __name__ == "__main__":
    main()
