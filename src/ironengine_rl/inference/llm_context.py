from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_ROLE_CONTRACT_FILE = "SOUL.md"
DEFAULT_SOUL_TEXT = """# IronEngine-RL LLM SOUL\n\nYou are the reasoning role inside IronEngine-RL. Your job is to interpret the active robot task, observation, repository context, action scheme, and safety limits, then produce reasoning that aligns with the framework workflow instead of bypassing it.\n\nCore duties:\n- stay task-oriented and keep the active user-defined robot task in view\n- reason in terms of IronEngine-RL concepts such as task phase, state estimate, reward hints, anomalies, and schedule notes\n- never invent a direct hardware command protocol or bypass the safety layer\n- treat the framework action scheme and safety constraints as hard boundaries\n- prefer concise, structured, execution-oriented reasoning over open-ended prose\n\nOutput alignment:\n- identify the next task phase that best fits the current evidence\n- surface important state or risk factors that the framework should know about\n- mention anomalies or uncertainty when they matter\n- support the configured task goal and success criteria\n- keep reasoning compatible with the framework's command-feedback-results workflow\n"""


def resolve_role_contract_reference(profile: dict[str, Any] | None, provider_cfg: dict[str, Any] | None) -> str:
    llm_cfg = profile.get("llm", {}) if isinstance(profile, dict) and isinstance(profile.get("llm"), dict) else {}
    provider_cfg = provider_cfg or {}
    return str(provider_cfg.get("role_contract_file") or llm_cfg.get("role_contract_file") or DEFAULT_ROLE_CONTRACT_FILE)


def load_role_contract(profile: dict[str, Any] | None, provider_cfg: dict[str, Any] | None) -> tuple[str, str, bool]:
    reference = resolve_role_contract_reference(profile, provider_cfg)
    path = Path(reference)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    if path.exists():
        return path.read_text(encoding="utf-8"), str(path), True
    return DEFAULT_SOUL_TEXT, reference, False


def resolve_llm_task(profile: dict[str, Any] | None, provider_cfg: dict[str, Any] | None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    provider_cfg = provider_cfg or {}
    context = context or {}
    llm_cfg = profile.get("llm", {}) if isinstance(profile, dict) and isinstance(profile.get("llm"), dict) else {}
    evaluation_cfg = profile.get("evaluation", {}) if isinstance(profile, dict) and isinstance(profile.get("evaluation"), dict) else {}
    task_spec = provider_cfg.get("task")
    if task_spec is None:
        task_spec = llm_cfg.get("task")
    if task_spec is None:
        task_spec = context.get("task")

    evaluation_task = evaluation_cfg.get("task")
    evaluation_name = _task_name_from_spec(evaluation_task)
    normalized = _normalize_task_spec(task_spec, fallback_name=evaluation_name)
    if not normalized["goal"]:
        normalized["goal"] = f"Complete the active framework task '{normalized['name']}' safely and efficiently."
    if not normalized["success_criteria"]:
        normalized["success_criteria"] = [
            "progress the robot toward the task goal without violating safety limits",
            "keep reasoning compatible with IronEngine-RL task phases and action scheduling",
        ]
    if not normalized["constraints"]:
        normalized["constraints"] = [
            "do not bypass IronEngine-RL safety boundaries or issue unsupported command formats",
            "stay consistent with available observations, action scheme, and repository context",
        ]
    if not normalized["output_requirements"]:
        normalized["output_requirements"] = [
            "align reasoning with task_phase, state_estimate, reward_hints, and anomalies",
            "support the framework workflow instead of replacing the agent or safety layer",
        ]
    return normalized


def build_role_and_task_preamble(profile: dict[str, Any] | None, provider_cfg: dict[str, Any] | None, context: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    role_contract_text, role_contract_ref, role_contract_loaded = load_role_contract(profile, provider_cfg)
    task = resolve_llm_task(profile, provider_cfg, context)
    preamble = (
        f"SOUL role contract source: {role_contract_ref}\n"
        f"SOUL contract loaded: {role_contract_loaded}\n"
        f"SOUL contract:\n{role_contract_text}\n\n"
        f"Active task name: {task['name']}\n"
        f"Active task goal: {task['goal']}\n"
        f"Success criteria: {task['success_criteria']}\n"
        f"Constraints: {task['constraints']}\n"
        f"Output requirements: {task['output_requirements']}\n"
    )
    return preamble, {
        "role_contract_file": role_contract_ref,
        "role_contract_loaded": role_contract_loaded,
        "task_name": task["name"],
        "task_goal": task["goal"],
        "task": task,
    }


def _normalize_task_spec(task_spec: Any, *, fallback_name: str) -> dict[str, Any]:
    if isinstance(task_spec, str):
        return {
            "name": fallback_name or "user_defined_task",
            "goal": task_spec,
            "success_criteria": [],
            "constraints": [],
            "output_requirements": [],
        }
    if isinstance(task_spec, dict):
        return {
            "name": str(task_spec.get("name", fallback_name or "user_defined_task")),
            "goal": str(task_spec.get("goal") or task_spec.get("instruction") or task_spec.get("objective") or ""),
            "success_criteria": list(task_spec.get("success_criteria", [])),
            "constraints": list(task_spec.get("constraints", [])),
            "output_requirements": list(task_spec.get("output_requirements", [])),
        }
    return {
        "name": fallback_name or "framework_task",
        "goal": "",
        "success_criteria": [],
        "constraints": [],
        "output_requirements": [],
    }


def _task_name_from_spec(task_spec: Any) -> str:
    if isinstance(task_spec, dict):
        return str(task_spec.get("name", task_spec.get("type", "framework_task")))
    if isinstance(task_spec, str):
        return task_spec
    return "framework_task"