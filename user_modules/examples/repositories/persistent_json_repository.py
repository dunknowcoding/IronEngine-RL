from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ironengine_rl.core.knowledge_repository import KnowledgeRepository
from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation, StepResult


class PersistentJsonRepository(KnowledgeRepository):
    def __init__(self, profile: dict[str, Any], run_dir: Path, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        super().__init__(profile=profile, run_dir=run_dir)
        file_name = str(self.config.get("database_file", "repository_database.json"))
        self.database_path = self.run_dir / file_name
        self._database = self._load_database()
        self._database.setdefault("transitions", [])
        self._database.setdefault("updates", [])
        self._database.setdefault("metadata", {})
        self._database["metadata"].update(
            {
                "repository_type": "persistent_json_repository",
                "action_scheme": self.profile.get("action_scheme", {}).get("name", "direct_channel_control"),
            }
        )
        self._flush_database()

    def record_transition(
        self,
        observation: Observation,
        inference: InferenceResult,
        action: ActionCommand,
        step_result: StepResult,
    ) -> None:
        super().record_transition(observation, inference, action, step_result)
        self._database["transitions"].append(
            {
                "observation": asdict(observation),
                "inference": asdict(inference),
                "command": action.command,
                "results": step_result.results,
            }
        )
        self._database["metadata"]["transition_count"] = len(self._database["transitions"])
        self._flush_database()

    def apply_update_instructions(self, instructions: dict[str, Any]) -> None:
        super().apply_update_instructions(instructions)
        self._database["updates"].append(dict(instructions))
        self._database["metadata"]["update_count"] = len(self._database["updates"])
        self._flush_database()

    def write_summary(self) -> Path:
        summary_path = super().write_summary()
        self._database["metadata"]["summary_path"] = str(summary_path)
        self._database["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
        self._flush_database()
        return summary_path

    def _load_database(self) -> dict[str, Any]:
        if not self.database_path.exists():
            return {}
        return json.loads(self.database_path.read_text(encoding="utf-8"))

    def _flush_database(self) -> None:
        self.database_path.write_text(json.dumps(self._database, indent=2), encoding="utf-8")
