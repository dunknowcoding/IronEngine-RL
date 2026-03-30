from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ironengine_rl.core.task_metrics import TaskMetricsAccumulator
from ironengine_rl.evaluations import evaluation_suite_from_profile
from ironengine_rl.framework.compatibility import build_compatibility_report
from ironengine_rl.framework.manifest import build_framework_manifest
from ironengine_rl.framework.platform_manifest import build_active_platform_manifest
from ironengine_rl.interfaces import ActionCommand, ActionScheme, InferenceResult, KnowledgeRepositoryPort, Observation, StepResult


def _action_scheme_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    scheme_cfg = dict(profile.get("action_scheme", {}))
    scheme = ActionScheme(
        name=str(scheme_cfg.get("name", "direct_channel_control")),
        command_channels=list(scheme_cfg.get("command_channels", [])),
        feedback_fields=list(scheme_cfg.get("feedback_fields", [])),
        result_fields=list(scheme_cfg.get("result_fields", [])),
        schedule_notes=list(scheme_cfg.get("schedule_notes", [])),
    )
    if not scheme.command_channels:
        capabilities = profile.get("platform", {}).get("capabilities", {})
        scheme.command_channels = list(capabilities.get("action_channels", []))
    if not scheme.feedback_fields:
        capabilities = profile.get("platform", {}).get("capabilities", {})
        scheme.feedback_fields = list(capabilities.get("observation_fields", []))
    return {
        "name": scheme.name,
        "command_channels": scheme.command_channels,
        "feedback_fields": scheme.feedback_fields,
        "result_fields": scheme.result_fields,
        "schedule_notes": scheme.schedule_notes,
    }


@dataclass(slots=True)
class KnowledgeRepository(KnowledgeRepositoryPort):
    profile: dict[str, Any]
    run_dir: Path
    action_graph: dict[str, list[str]] = field(default_factory=lambda: {"approach": ["grasp"], "grasp": ["stabilize"], "stabilize": []})
    repository_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.transition_log = self.run_dir / "transitions.jsonl"
        self.update_log = self.run_dir / "updates.jsonl"
        self.task_metrics = TaskMetricsAccumulator()
        self.framework_manifest = build_framework_manifest(self.profile)
        self.platform_manifest = build_active_platform_manifest(self.profile)
        self.compatibility_report = build_compatibility_report(self.profile, self.framework_manifest, self.platform_manifest)
        self.evaluation_suite = evaluation_suite_from_profile(self.profile)
        self.summary = {
            "episodes": 0,
            "successes": 0,
            "reward_total": 0.0,
            "known_components": self.profile.get("future_components", []),
        }

    def build_context(self) -> dict[str, Any]:
        action_scheme = _action_scheme_from_profile(self.profile)
        return {
            "action_graph": self.action_graph,
            "repository_notes": list(self.repository_notes),
            "known_components": self.summary["known_components"],
            "success_rate": self._success_rate(),
            "knowledge_repository": {
                "type": self.profile.get("repository", {}).get("type", "knowledge_repository"),
                "run_dir": str(self.run_dir),
            },
            "database": {
                "enabled": self.profile.get("repository", {}).get("type") == "custom_plugin",
                "mode": "example_plugin" if self.profile.get("repository", {}).get("type") == "custom_plugin" else "ephemeral_memory",
            },
            "action_scheme": action_scheme,
            "evaluation": self.evaluation_suite.summary(
                episodes=self.summary["episodes"],
                successes=self.summary["successes"],
                reward_total=self.summary["reward_total"],
            ),
            "framework_manifest": self.framework_manifest,
            "platform_manifest": self.platform_manifest,
            "compatibility": self.compatibility_report,
        }

    def record_transition(
        self,
        observation: Observation,
        inference: InferenceResult,
        action: ActionCommand,
        step_result: StepResult,
    ) -> None:
        entry = {
            "observation": asdict(observation),
            "inference": asdict(inference),
            "action": asdict(action),
            "step_result": {
                "reward": step_result.reward.total,
                "reward_components": step_result.reward.components,
                "done": step_result.done,
                "info": step_result.info,
            },
        }
        with self.transition_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        self.summary["reward_total"] += step_result.reward.total
        self.task_metrics.update(action, step_result)
        self.evaluation_suite.update(action, step_result)
        if step_result.done:
            self.summary["episodes"] += 1
            if step_result.info.get("success"):
                self.summary["successes"] += 1
                self.repository_notes.append("Successful grasp sequence observed.")
            else:
                self.repository_notes.append("Episode ended without grasp; revisit approach policy.")

    def apply_update_instructions(self, instructions: dict[str, Any]) -> None:
        if note := instructions.get("note"):
            self.repository_notes.append(str(note))
        if action_graph := instructions.get("action_graph"):
            self.action_graph.update(action_graph)
        with self.update_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(instructions) + "\n")

    def write_summary(self) -> Path:
        summary_path = self.run_dir / "summary.json"
        payload = dict(self.summary)
        payload["success_rate"] = self._success_rate()
        payload["task_metrics"] = self.task_metrics.to_summary(
            episodes=self.summary["episodes"],
            successes=self.summary["successes"],
            reward_total=self.summary["reward_total"],
        )
        payload["framework_manifest"] = self.framework_manifest
        payload["platform_manifest"] = self.platform_manifest
        payload["compatibility"] = self.compatibility_report
        payload["evaluation"] = self.evaluation_suite.summary(
            episodes=self.summary["episodes"],
            successes=self.summary["successes"],
            reward_total=self.summary["reward_total"],
        )
        payload["repository_notes"] = self.repository_notes[-10:]
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return summary_path

    def _success_rate(self) -> float:
        episodes = self.summary["episodes"]
        return self.summary["successes"] / episodes if episodes else 0.0
