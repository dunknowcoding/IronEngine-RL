from __future__ import annotations

from typing import Any


def compute_boundary_conditions(profile: dict[str, Any]) -> dict[str, Any]:
    from .boundaries import compute_boundary_conditions as _impl

    return _impl(profile)


def build_compatibility_report(
    profile: dict[str, object],
    framework_manifest: dict[str, object],
    platform_manifest: dict[str, object],
) -> dict[str, object]:
    from .compatibility import build_compatibility_report as _impl

    return _impl(profile, framework_manifest, platform_manifest)


def build_framework_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    from .manifest import build_framework_manifest as _impl

    return _impl(profile)


def build_active_platform_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    from .platform_manifest import build_active_platform_manifest as _impl

    return _impl(profile)


def build_validation_report(profile: dict[str, Any]) -> dict[str, Any]:
    from .validation import build_validation_report as _impl

    return _impl(profile)


def validate_profile_schema(profile: dict[str, Any]) -> dict[str, Any]:
    from .validation import validate_profile_schema as _impl

    return _impl(profile)

__all__ = [
    "build_active_platform_manifest",
    "build_compatibility_report",
    "build_framework_manifest",
    "build_validation_report",
    "compute_boundary_conditions",
    "validate_profile_schema",
]
