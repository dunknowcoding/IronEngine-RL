from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl.core import KnowledgeRepository


class RepositoryTest(unittest.TestCase):
    def test_update_instruction_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = KnowledgeRepository(profile={"future_components": ["depth_sensor"]}, run_dir=Path(temp_dir))
            repository.apply_update_instructions({"note": "new policy candidate", "action_graph": {"grasp": ["stabilize", "lift"]}})
            update_log = Path(temp_dir) / "updates.jsonl"
            self.assertTrue(update_log.exists())
            lines = update_log.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["note"], "new policy candidate")


if __name__ == "__main__":
    unittest.main()
