from __future__ import annotations

import argparse
import json
import sys

from ironengine_rl.core import RuntimeOrchestrator
from ironengine_rl.framework import build_validation_report
from ironengine_rl.config import load_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IronEngine-RL runtime")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    parser.add_argument("--episodes", type=int, default=1, help="Number of episodes")
    parser.add_argument("--steps", type=int, default=None, help="Optional maximum steps per episode")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the profile and exit")
    parser.add_argument("--strict", action="store_true", help="Exit with a non-zero code when validation finds issues")
    parser.add_argument("--skip-compatibility", action="store_true", help="Report schema validation only")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.validate_only:
        profile = load_profile(args.profile)
        report = build_validation_report(profile)
        print(json.dumps(report, indent=2))
        is_valid = report.get("schema", {}).get("valid", False)
        if not args.skip_compatibility:
            is_valid = is_valid and report.get("compatibility", {}).get("compatible", False)
        if args.strict and not is_valid:
            raise SystemExit(1)
        return
    orchestrator = RuntimeOrchestrator(profile_path=args.profile)
    result = orchestrator.run(episodes=args.episodes, max_steps=args.steps)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
