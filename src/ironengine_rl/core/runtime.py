from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ironengine_rl.config import load_profile
from ironengine_rl.core.inference_engine import InferenceEngine
from ironengine_rl.framework.factories import build_runtime_components
from ironengine_rl.framework.validation import build_validation_report


@dataclass(slots=True)
class RuntimeOrchestrator:
    profile_path: str

    def run(self, episodes: int, max_steps: int | None = None) -> dict[str, Any]:
        profile = load_profile(self.profile_path)
        runtime_cfg = profile.get("runtime", {})
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(profile.get("logs", {}).get("run_dir", "logs")) / timestamp
        validation_report = build_validation_report(profile)
        framework_manifest = validation_report["framework_manifest"]
        platform_manifest = validation_report["platform_manifest"]
        compatibility = validation_report["compatibility"]
        validation_cfg = profile.get("validation", {})
        if validation_cfg.get("strict", False):
            if not validation_report.get("schema", {}).get("valid", False):
                raise ValueError(f"Invalid profile definition: {validation_report['schema']['issues']}")
            if validation_cfg.get("require_compatibility", True) and not compatibility.get("compatible", False):
                raise ValueError(f"Incompatible profile/platform configuration: {compatibility['issues']}")
        components = build_runtime_components(profile, run_dir=run_dir)
        repository = components.repository
        repository.framework_manifest = framework_manifest
        repository.platform_manifest = platform_manifest
        repository.compatibility_report = compatibility
        inference_engine = InferenceEngine(model_provider=components.provider)
        requested_steps = max_steps or int(profile.get("simulator", {}).get("max_steps", 50))
        for episode in range(episodes):
            observation = components.environment.reset()
            components.safety.reset()
            repository.apply_update_instructions({"note": f"Episode {episode + 1} started in stage {runtime_cfg.get('stage', 'A')}"})
            for _ in range(requested_steps):
                context = repository.build_context()
                inference = inference_engine.infer(observation, context)
                action = components.agent.act(observation, inference, context)
                safe_action = components.safety.apply(action, observation, inference)
                step_result = components.environment.step(safe_action)
                repository.record_transition(observation, inference, safe_action, step_result)
                observation = step_result.observation
                if step_result.done:
                    break
        summary_path = repository.write_summary()
        return {"summary_path": str(summary_path), "run_dir": str(run_dir)}
