from __future__ import annotations

from pathlib import Path
from typing import Any

from ironengine_rl.framework.compatibility import build_compatibility_report
from ironengine_rl.framework.manifest import build_framework_manifest
from ironengine_rl.framework.platform_manifest import build_active_platform_manifest


CONTRACT_LIST_FIELDS = {
    "observation_fields",
    "camera_roles",
    "action_channels",
    "repository_context_keys",
    "runtime_modes",
}


def validate_profile_schema(profile: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    _validate_dict_sections(
        profile,
        issues,
        [
            "runtime",
            "hardware",
            "action_scheme",
            "simulator",
            "vision",
            "model_provider",
            "evaluation",
            "agent",
            "repository",
            "boundary_conditions",
            "platform",
            "validation",
            "llm",
        ],
    )
    _validate_hardware_group(profile.get("hardware"), issues)
    _validate_metrics(profile, issues)
    _validate_contract_override("model_provider.contract", profile.get("model_provider", {}).get("contract"), issues)
    _validate_contract_override("agent.contract", profile.get("agent", {}).get("contract"), issues)
    _validate_contract_override("boundary_conditions.contract", profile.get("boundary_conditions", {}).get("contract"), issues)
    _validate_contract_override(
        "model_provider.update_strategy.contract",
        profile.get("model_provider", {}).get("update_strategy", {}).get("contract"),
        issues,
    )
    task_spec = profile.get("evaluation", {}).get("task")
    if isinstance(task_spec, dict):
        _validate_contract_override("evaluation.task.contract", task_spec.get("contract"), issues)
    _validate_plugin_host("model_provider", profile.get("model_provider", {}), issues)
    _validate_plugin_host("agent", profile.get("agent", {}), issues)
    _validate_plugin_host("repository", profile.get("repository", {}), issues)
    _validate_plugin_host("boundary_conditions", profile.get("boundary_conditions", {}), issues)
    _validate_plugin_host("model_provider.update_strategy", profile.get("model_provider", {}).get("update_strategy", {}), issues)
    if isinstance(task_spec, dict):
        _validate_plugin_host("evaluation.task", task_spec, issues)
    for index, metric_spec in enumerate(profile.get("evaluation", {}).get("metrics", [])):
        if isinstance(metric_spec, dict):
            _validate_plugin_host(f"evaluation.metrics[{index}]", metric_spec, issues)
            _validate_contract_override(f"evaluation.metrics[{index}].contract", metric_spec.get("contract"), issues)
    _validate_action_scheme(profile.get("action_scheme"), issues)
    _validate_prompt_update_warning(profile.get("model_provider", {}), issues)
    _validate_llm_configuration(profile, issues)
    _validate_platform_capabilities(profile.get("platform", {}).get("capabilities"), issues)
    return {"valid": not any(issue.get("severity") == "error" for issue in issues), "issues": issues}


def build_validation_report(profile: dict[str, Any]) -> dict[str, Any]:
    schema = validate_profile_schema(profile)
    framework_manifest: dict[str, Any] = {}
    platform_manifest: dict[str, Any] = {}
    compatibility: dict[str, Any] = {
        "compatible": False,
        "issues": [
            {
                "severity": "error",
                "code": "schema_validation_failed",
                "message": "Compatibility checks skipped until schema issues are resolved.",
                "details": {},
            }
        ],
        "checked_components": {},
    }
    if schema["valid"]:
        try:
            framework_manifest = build_framework_manifest(profile)
            platform_manifest = build_active_platform_manifest(profile)
            compatibility = build_compatibility_report(profile, framework_manifest, platform_manifest)
        except Exception as exc:
            schema["valid"] = False
            schema["issues"].append(
                {
                    "severity": "error",
                    "code": "validation_build_failed",
                    "message": str(exc),
                    "details": {"exception_type": type(exc).__name__},
                }
            )
    return {
        "valid": schema["valid"] and compatibility.get("compatible", False),
        "schema": schema,
        "framework_manifest": framework_manifest,
        "platform_manifest": platform_manifest,
        "compatibility": compatibility,
    }


def _validate_dict_sections(profile: dict[str, Any], issues: list[dict[str, Any]], section_names: list[str]) -> None:
    for section_name in section_names:
        value = profile.get(section_name)
        if value is not None and not isinstance(value, dict):
            issues.append(_issue("error", "invalid_section_type", f"Section '{section_name}' must be an object.", {"section": section_name}))


def _validate_metrics(profile: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    metrics = profile.get("evaluation", {}).get("metrics", [])
    if not isinstance(metrics, list):
        issues.append(_issue("error", "invalid_metrics_type", "'evaluation.metrics' must be a list.", {"value_type": type(metrics).__name__}))


def _validate_plugin_host(path: str, config: Any, issues: list[dict[str, Any]]) -> None:
    if not isinstance(config, dict):
        return
    if config.get("type") != "custom_plugin":
        return
    plugin = config.get("plugin")
    if not isinstance(plugin, dict):
        issues.append(_issue("error", "missing_plugin_spec", f"'{path}' must define a plugin object for custom plugins.", {"path": path}))
        return
    has_module_path = bool(plugin.get("module_path"))
    has_file_path = bool(plugin.get("file_path"))
    if not (has_module_path or has_file_path):
        issues.append(_issue("error", "invalid_plugin_spec", f"'{path}.plugin' must define 'module_path' or 'file_path'.", {"path": path}))


def _validate_contract_override(path: str, contract: Any, issues: list[dict[str, Any]]) -> None:
    if contract is None:
        return
    if not isinstance(contract, dict):
        issues.append(_issue("error", "invalid_contract_type", f"'{path}' must be an object.", {"path": path}))
        return
    for key, value in contract.items():
        if key in CONTRACT_LIST_FIELDS and not isinstance(value, list):
            issues.append(_issue("error", "invalid_contract_field", f"'{path}.{key}' must be a list.", {"path": path, "field": key}))


def _validate_platform_capabilities(capabilities: Any, issues: list[dict[str, Any]]) -> None:
    if capabilities is None:
        return
    if not isinstance(capabilities, dict):
        issues.append(_issue("error", "invalid_platform_capabilities", "'platform.capabilities' must be an object.", {}))
        return
    for field_name in ["transport_backends", "observation_fields", "camera_roles", "action_channels", "safety_features"]:
        value = capabilities.get(field_name)
        if value is not None and not isinstance(value, list):
            issues.append(_issue("error", "invalid_capability_field", f"'platform.capabilities.{field_name}' must be a list.", {"field": field_name}))
    timing = capabilities.get("timing")
    if timing is not None and not isinstance(timing, dict):
        issues.append(_issue("error", "invalid_capability_timing", "'platform.capabilities.timing' must be an object.", {}))


def _validate_hardware_group(hardware: Any, issues: list[dict[str, Any]]) -> None:
    if hardware is None:
        return
    if not isinstance(hardware, dict):
        issues.append(_issue("error", "invalid_hardware_section", "'hardware' must be an object.", {}))
        return
    for field_name in ["platform", "connection", "protocol", "cameras", "safety", "mock"]:
        value = hardware.get(field_name)
        if value is not None and not isinstance(value, dict):
            issues.append(_issue("error", "invalid_hardware_group", f"'hardware.{field_name}' must be an object.", {"field": field_name}))
    mock_cfg = hardware.get("mock")
    if isinstance(mock_cfg, dict):
        packets = mock_cfg.get("packets")
        scenarios = mock_cfg.get("scenarios")
        if packets is not None and not isinstance(packets, list):
            issues.append(_issue("error", "invalid_hardware_mock_packets", "'hardware.mock.packets' must be a list.", {}))
        if scenarios is not None and not isinstance(scenarios, dict):
            issues.append(_issue("error", "invalid_hardware_mock_scenarios", "'hardware.mock.scenarios' must be an object.", {}))


def _validate_action_scheme(action_scheme: Any, issues: list[dict[str, Any]]) -> None:
    if action_scheme is None:
        return
    if not isinstance(action_scheme, dict):
        issues.append(_issue("error", "invalid_action_scheme", "'action_scheme' must be an object.", {}))
        return
    for field_name in ["command_channels", "feedback_fields", "result_fields", "schedule_notes"]:
        value = action_scheme.get(field_name)
        if value is not None and not isinstance(value, list):
            issues.append(_issue("error", "invalid_action_scheme_field", f"'action_scheme.{field_name}' must be a list.", {"field": field_name}))


def _validate_prompt_update_warning(model_provider: Any, issues: list[dict[str, Any]]) -> None:
    if not isinstance(model_provider, dict):
        return
    provider_type = model_provider.get("type")
    update_strategy = model_provider.get("update_strategy")
    if provider_type not in {"ollama_prompt", "lmstudio_prompt", "cloud_prompt"}:
        return
    if not isinstance(update_strategy, dict) or update_strategy.get("type", "none") == "none":
        return
    issues.append(
        _issue(
            "warning",
            "llm_update_strategy_ignored",
            "Prompt-driven providers ignore 'model_provider.update_strategy'; the setting is retained for reference only.",
            {"provider_type": provider_type, "update_strategy": update_strategy.get("type")},
        )
    )


def _validate_llm_configuration(profile: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    llm_cfg = profile.get("llm")
    if llm_cfg is not None and not isinstance(llm_cfg, dict):
        issues.append(_issue("error", "invalid_llm_section", "'llm' must be an object.", {}))
        return
    if isinstance(llm_cfg, dict):
        _validate_task_spec("llm.task", llm_cfg.get("task"), issues)
        _validate_role_contract_file("llm.role_contract_file", llm_cfg.get("role_contract_file"), issues)
    model_provider = profile.get("model_provider", {})
    if isinstance(model_provider, dict):
        _validate_task_spec("model_provider.task", model_provider.get("task"), issues)
        _validate_role_contract_file("model_provider.role_contract_file", model_provider.get("role_contract_file"), issues)


def _validate_task_spec(path: str, task_spec: Any, issues: list[dict[str, Any]]) -> None:
    if task_spec is None:
        return
    if isinstance(task_spec, str):
        return
    if not isinstance(task_spec, dict):
        issues.append(_issue("error", "invalid_task_spec", f"'{path}' must be a string or object.", {"path": path}))
        return
    for field_name in ["success_criteria", "constraints", "output_requirements"]:
        value = task_spec.get(field_name)
        if value is not None and not isinstance(value, list):
            issues.append(_issue("error", "invalid_task_field", f"'{path}.{field_name}' must be a list.", {"path": path, "field": field_name}))


def _validate_role_contract_file(path: str, value: Any, issues: list[dict[str, Any]]) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        issues.append(_issue("error", "invalid_role_contract_file", f"'{path}' must be a string path.", {"path": path}))
        return
    file_path = Path(value)
    if not file_path.is_absolute():
        file_path = Path(__file__).resolve().parents[3] / file_path
    if not file_path.exists():
        issues.append(_issue("warning", "missing_role_contract_file", f"'{path}' does not exist; the built-in SOUL fallback text will be used.", {"path": path, "file": value}))


def _issue(severity: str, code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "details": details,
    }
