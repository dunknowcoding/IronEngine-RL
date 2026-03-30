from __future__ import annotations

from typing import Any

from ironengine_rl.inference.registry import provider_from_profile as registry_provider_from_profile


def provider_from_profile(profile: dict[str, Any]):
    return registry_provider_from_profile(profile)
