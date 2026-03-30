from __future__ import annotations

from typing import Any

from ironengine_rl.platforms import build_platform_manifest


def build_active_platform_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    return build_platform_manifest(profile)
