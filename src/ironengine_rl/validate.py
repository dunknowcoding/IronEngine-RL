from __future__ import annotations

import argparse
import json

from ironengine_rl.config import load_profile
from ironengine_rl.framework.validation import build_validation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an IronEngine-RL profile without running episodes")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    parser.add_argument("--strict", action="store_true", help="Exit with a non-zero code when validation fails")
    parser.add_argument("--skip-compatibility", action="store_true", help="Only enforce schema validation")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    profile = load_profile(args.profile)
    report = build_validation_report(profile)
    print(json.dumps(report, indent=2))
    is_valid = report.get("schema", {}).get("valid", False)
    if not args.skip_compatibility:
        is_valid = is_valid and report.get("compatibility", {}).get("compatible", False)
    if args.strict and not is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
