from __future__ import annotations

import argparse
import json

from ironengine_rl.config import load_profile
from ironengine_rl.framework import build_validation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Describe IronEngine-RL module configuration and interfaces")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    profile = load_profile(args.profile)
    print(json.dumps(build_validation_report(profile), indent=2))


if __name__ == "__main__":
    main()
