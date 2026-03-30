from __future__ import annotations

from typing import Any

from ironengine_rl.contracts import InterfaceContract
from ironengine_rl.evaluations import describe_available_evaluations
from ironengine_rl.framework.boundaries import compute_boundary_conditions
from ironengine_rl.inference.llm_context import resolve_llm_task, resolve_role_contract_reference
from ironengine_rl.inference import describe_available_inference_modules
from ironengine_rl.training import describe_available_update_strategies


def build_framework_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    model_cfg = profile.get("model_provider", {})
    evaluation_cfg = profile.get("evaluation", {})
    agent_cfg = profile.get("agent", {})
    boundary_cfg = profile.get("boundary_conditions", profile.get("safety", {}))
    runtime_mode = profile.get("runtime", {}).get("mode", "simulation")
    provider_type = model_cfg.get("type", "rule_based")
    provider_style = _provider_style(provider_type)
    action_scheme = _resolve_action_scheme(profile)
    llm_task = resolve_llm_task(profile, model_cfg) if provider_style == "prompt_engineering" or profile.get("llm") else {}
    llm_role_contract = resolve_role_contract_reference(profile, model_cfg) if provider_style == "prompt_engineering" or profile.get("llm") else ""
    interface_requirements = {
        "observation_fields": [
            "object_dx",
            "object_dy",
            "claw_alignment",
            "arm_extension",
            "arm_height",
            "battery_level",
            "collision_risk",
        ],
        "camera_roles": ["dash", "claw"],
        "action_channels": [
            "chassis_forward",
            "chassis_strafe",
            "chassis_turn",
            "arm_lift",
            "arm_extend",
            "wrist_yaw",
            "gripper_close",
        ],
        "repository_context_keys": [
            "action_graph",
            "repository_notes",
            "known_components",
            "success_rate",
            "evaluation",
            "framework_manifest",
            "platform_manifest",
            "compatibility",
        ],
        "command_channels": list(action_scheme["command_channels"]),
        "feedback_fields": list(action_scheme["feedback_fields"]),
        "result_fields": list(action_scheme["result_fields"]),
        "action_scheme": action_scheme,
        "naming_aliases": {
            "command": "action_channels",
            "feedback": "observation_fields",
            "results": "result_fields",
            "knowledge_repository": "repository_context_keys",
        },
        "model_style": provider_style,
        "prompt_engineering_required": provider_style == "prompt_engineering",
        "pytorch_required": provider_style == "trainable_weights",
        "runtime_mode": runtime_mode,
        "llm_task": llm_task,
        "llm_role_contract_file": llm_role_contract,
    }
    active_modules = {
        "evaluation": _module_manifest_entry(
            name=_task_name(evaluation_cfg.get("task", "tabletop_grasp")),
            module_type="evaluation",
            style="task",
            contract=_contract_with_overrides(
                InterfaceContract(
                observation_fields=["object_dx", "object_dy", "claw_alignment", "arm_extension", "arm_height"],
                camera_roles=["dash", "claw"],
                runtime_modes=[runtime_mode],
                ),
                _task_contract_overrides(evaluation_cfg.get("task", "tabletop_grasp")),
            ),
            config={"metrics": evaluation_cfg.get("metrics", ["task_performance", "boundary_violations"])},
        ),
        "inference_engine": _module_manifest_entry(
            name=provider_type,
            module_type="inference_engine",
            style=provider_style,
            contract=_contract_with_overrides(
                InterfaceContract(
                observation_fields=interface_requirements["observation_fields"],
                camera_roles=interface_requirements["camera_roles"],
                repository_context_keys=interface_requirements["repository_context_keys"],
                runtime_modes=[runtime_mode],
                ),
                model_cfg.get("contract", {}),
            ),
            config=_safe_config_view(model_cfg),
        ),
        "agent": _module_manifest_entry(
            name=agent_cfg.get("type", "heuristic"),
            module_type="agent",
            style="policy",
            contract=_contract_with_overrides(
                InterfaceContract(
                action_channels=interface_requirements["action_channels"],
                repository_context_keys=interface_requirements["repository_context_keys"],
                runtime_modes=[runtime_mode],
                ),
                agent_cfg.get("contract", {}),
            ),
            config=_safe_config_view(agent_cfg),
        ),
        "repository": _module_manifest_entry(
            name=profile.get("repository", {}).get("type", "knowledge_repository"),
            module_type="repository",
            style="memory_or_plugin",
            contract=InterfaceContract(
                repository_context_keys=interface_requirements["repository_context_keys"],
                runtime_modes=[runtime_mode],
            ).to_dict(),
            config=_safe_config_view(profile.get("repository", {})),
        ),
        "boundary_conditions": _module_manifest_entry(
            name=boundary_cfg.get("type", "safety_controller"),
            module_type="boundary_conditions",
            style="safety",
            contract=_contract_with_overrides(
                InterfaceContract(
                observation_fields=["battery_level", "collision_risk", "arm_extension", "gripper_close"],
                action_channels=interface_requirements["action_channels"],
                runtime_modes=[runtime_mode],
                ),
                boundary_cfg.get("contract", {}),
            ),
            config=_safe_config_view(boundary_cfg),
        ),
        "update_strategy": _module_manifest_entry(
            name=model_cfg.get("update_strategy", {}).get("type", "none"),
            module_type="update_strategy",
            style="adaptation",
            contract=_contract_with_overrides(
                InterfaceContract(runtime_modes=[runtime_mode]),
                model_cfg.get("update_strategy", {}).get("contract", {}),
            ),
            config=_safe_config_view(model_cfg.get("update_strategy", {})),
        ),
    }
    return {
        "active_modules": active_modules,
        "interface_requirements": interface_requirements,
        "boundary_conditions": compute_boundary_conditions(profile),
        "available_modules": {
            "evaluations": describe_available_evaluations(),
            "inference_engines": describe_available_inference_modules(),
            "update_strategies": describe_available_update_strategies(),
        },
    }


def _provider_style(provider_type: str) -> str:
    if provider_type in {"ollama_prompt", "lmstudio_prompt", "cloud_prompt"}:
        return "prompt_engineering"
    if provider_type in {"custom_model", "linear_policy", "pytorch_trainable", "custom_plugin"}:
        return "trainable_weights" if provider_type != "custom_plugin" else "custom"
    return "heuristic_or_rules"


def _resolve_action_scheme(profile: dict[str, Any]) -> dict[str, Any]:
    scheme_cfg = profile.get("action_scheme", {})
    default_channels = [
        "chassis_forward",
        "chassis_strafe",
        "chassis_turn",
        "arm_lift",
        "arm_extend",
        "wrist_yaw",
        "gripper_close",
    ]
    default_feedback = [
        "object_dx",
        "object_dy",
        "claw_alignment",
        "arm_extension",
        "arm_height",
        "battery_level",
        "collision_risk",
    ]
    return {
        "name": str(scheme_cfg.get("name", "direct_channel_control")),
        "command_channels": list(scheme_cfg.get("command_channels", default_channels)),
        "feedback_fields": list(scheme_cfg.get("feedback_fields", default_feedback)),
        "result_fields": list(scheme_cfg.get("result_fields", ["reward.total", "reward.components", "done", "info"])),
        "schedule_notes": list(scheme_cfg.get("schedule_notes", [])),
    }


def _module_manifest_entry(*, name: str, module_type: str, style: str, contract: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "type": module_type,
        "style": style,
        "contract": contract,
        "config": config,
    }


def _safe_config_view(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key not in {"api_key", "token", "secret"}}


def _contract_with_overrides(default_contract: InterfaceContract, overrides: dict[str, Any] | None) -> dict[str, Any]:
    contract = default_contract.to_dict()
    for key, value in (overrides or {}).items():
        if key in contract:
            contract[key] = value
    return contract


def _task_contract_overrides(task_spec: Any) -> dict[str, Any]:
    if isinstance(task_spec, dict):
        return dict(task_spec.get("contract", {}))
    return {}


def _task_name(task_spec: Any) -> str:
    if isinstance(task_spec, dict):
        return str(task_spec.get("name", task_spec.get("type", "custom_task")))
    return str(task_spec)
