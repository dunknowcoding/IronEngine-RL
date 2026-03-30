from __future__ import annotations

from ironengine_rl.contracts import CompatibilityIssue, CompatibilityReport


def build_compatibility_report(
    profile: dict[str, object],
    framework_manifest: dict[str, object],
    platform_manifest: dict[str, object],
) -> dict[str, object]:
    issues: list[CompatibilityIssue] = []
    modules = framework_manifest.get("active_modules", {})
    runtime_modes = _normalize_runtime_modes([str(profile.get("runtime", {}).get("mode", "simulation"))])
    for module_name, module_data in modules.items():
        if not isinstance(module_data, dict):
            continue
        contract = module_data.get("contract", {})
        _check_runtime_mode(module_name, contract, runtime_modes, issues)
        _check_list_requirement(module_name, "observation_fields", contract, platform_manifest, issues)
        _check_list_requirement(module_name, "camera_roles", contract, platform_manifest, issues)
        _check_list_requirement(module_name, "action_channels", contract, platform_manifest, issues)
    report = CompatibilityReport(
        compatible=not any(issue.severity == "error" for issue in issues),
        issues=issues,
        checked_components={
            "platform": platform_manifest.get("name"),
            "runtime_mode": profile.get("runtime", {}).get("mode", "simulation"),
            "modules": sorted(modules.keys()),
        },
    )
    return report.to_dict()


def _check_runtime_mode(module_name: str, contract: dict[str, object], runtime_modes: set[str], issues: list[CompatibilityIssue]) -> None:
    supported = _normalize_runtime_modes([str(mode) for mode in contract.get("runtime_modes", [])])
    if supported and not (supported & runtime_modes):
        issues.append(
            CompatibilityIssue(
                severity="error",
                code="runtime_mode_mismatch",
                message=f"Module '{module_name}' does not support the active runtime mode.",
                details={"supported": sorted(supported), "active": sorted(runtime_modes)},
            )
        )


def _check_list_requirement(
    module_name: str,
    key: str,
    contract: dict[str, object],
    platform_manifest: dict[str, object],
    issues: list[CompatibilityIssue],
) -> None:
    required = {str(item) for item in contract.get(key, [])}
    provided = {str(item) for item in platform_manifest.get(key, [])}
    missing = sorted(required - provided)
    if missing:
        issues.append(
            CompatibilityIssue(
                severity="error",
                code=f"missing_{key}",
                message=f"Platform is missing required {key} for module '{module_name}'.",
                details={"missing": missing, "provided": sorted(provided)},
            )
        )


def _normalize_runtime_modes(values: list[str]) -> set[str]:
    normalized = {value for value in values if value}
    if "hardware" in normalized:
        normalized.add("real")
    if "real" in normalized:
        normalized.add("hardware")
    return normalized
