from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl.config import load_profile
from ironengine_rl.core import RuntimeOrchestrator
from ironengine_rl.framework import build_validation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the task-oriented multi-object grasp example.")
    parser.add_argument(
        "--profile",
        default="examples/inference/task_oriented_multi_object_grasp/profile.json",
        help="Path to the example profile.",
    )
    parser.add_argument("--episodes", type=int, default=1, help="Number of episodes to run.")
    parser.add_argument("--steps", type=int, default=16, help="Maximum steps per episode.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the profile and print the report.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    profile_path = (repo_root / args.profile).resolve()
    profile = load_profile(profile_path)
    report = build_validation_report(profile)
    if args.validate_only:
        print(json.dumps(report, indent=2))
        return
    if not report["schema"]["valid"] or not report["compatibility"].get("compatible", False):
        print(json.dumps({"status": "invalid_profile", "validation": report}, indent=2))
        raise SystemExit(1)
    result = RuntimeOrchestrator(profile_path=str(profile_path)).run(episodes=args.episodes, max_steps=args.steps)
    print(json.dumps({"status": "completed", "profile": str(profile_path), **result}, indent=2))


if __name__ == "__main__":
    main()
