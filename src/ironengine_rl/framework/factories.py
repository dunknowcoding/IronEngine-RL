from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ironengine_rl.core.agent import HeuristicAgent
from ironengine_rl.core.knowledge_repository import KnowledgeRepository
from ironengine_rl.core.safety import SafetyController
from ironengine_rl.evaluations import evaluation_suite_from_profile
from ironengine_rl.inference import provider_from_profile
from ironengine_rl.platforms import platform_adapter_from_profile
from ironengine_rl.plugins import instantiate_plugin


@dataclass(slots=True)
class RuntimeComponents:
    environment: Any
    provider: Any
    agent: Any
    safety: Any
    repository: Any
    evaluation_suite: Any


def build_runtime_components(profile: dict[str, Any], run_dir: Path | None = None) -> RuntimeComponents:
    repository = _repository_from_profile(profile, run_dir=run_dir)
    provider = provider_from_profile(profile)
    agent = _agent_from_profile(profile)
    safety = _safety_from_profile(profile)
    environment = platform_adapter_from_profile(profile).build_environment(profile)
    evaluation_suite = evaluation_suite_from_profile(profile)
    return RuntimeComponents(
        environment=environment,
        provider=provider,
        agent=agent,
        safety=safety,
        repository=repository,
        evaluation_suite=evaluation_suite,
    )


def _repository_from_profile(profile: dict[str, Any], run_dir: Path | None = None) -> Any:
    repository_cfg = profile.get("repository", {})
    repository_type = repository_cfg.get("type", "knowledge_repository")
    resolved_run_dir = run_dir or Path(profile.get("logs", {}).get("run_dir", "logs"))
    if repository_type == "custom_plugin":
        return instantiate_plugin(repository_cfg.get("plugin", {}), profile=profile, run_dir=resolved_run_dir, config=repository_cfg)
    if repository_type in {"knowledge_repository", "default"}:
        return KnowledgeRepository(profile=profile, run_dir=resolved_run_dir)
    raise ValueError(f"Unsupported repository type: {repository_type}")


def _agent_from_profile(profile: dict[str, Any]) -> Any:
    agent_cfg = profile.get("agent", {})
    agent_type = agent_cfg.get("type", "heuristic")
    if agent_type == "custom_plugin":
        return instantiate_plugin(agent_cfg.get("plugin", {}), profile=profile, config=agent_cfg)
    if agent_type == "heuristic":
        return HeuristicAgent(profile)
    raise ValueError(f"Unsupported agent type: {agent_type}")


def _safety_from_profile(profile: dict[str, Any]) -> Any:
    boundary_cfg = profile.get("boundary_conditions", profile.get("safety", {}))
    boundary_type = boundary_cfg.get("type", "safety_controller")
    if boundary_type == "custom_plugin":
        return instantiate_plugin(boundary_cfg.get("plugin", {}), profile=profile, config=boundary_cfg)
    if boundary_type in {"safety_controller", "default"}:
        return SafetyController(profile)
    raise ValueError(f"Unsupported boundary condition type: {boundary_type}")
