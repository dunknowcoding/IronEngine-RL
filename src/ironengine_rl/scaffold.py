from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PRESET_NAMES = ["default", "wheeled_arm", "arm_only", "visionless_link_monitor"]
GUIDED_GOALS = ["custom_hardware", "armsmart_hardware", "local_ollama", "cloud_api", "custom_pytorch"]
DEFAULT_ACTION_CHANNELS = ["chassis_forward", "chassis_strafe", "chassis_turn", "arm_lift", "arm_extend", "wrist_yaw", "gripper_close"]
DEFAULT_FEEDBACK_FIELDS = ["object_dx", "object_dy", "claw_alignment", "arm_extension", "arm_height", "battery_level", "collision_risk"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold a new hardware integration profile for IronEngine-RL")
    parser.add_argument("--output", required=True, help="Path to write the scaffolded profile JSON")
    parser.add_argument("--example", choices=["template", "armsmart_mock", "armsmart_hil"], default="template", help="Base example profile to copy")
    parser.add_argument("--preset", choices=PRESET_NAMES, default="default", help="Optional hardware topology preset to apply after loading the base example")
    parser.add_argument("--guided-goal", choices=GUIDED_GOALS, default=None, help="Choose a goal-oriented scaffold flow for custom hardware, ARMSmart hardware, local Ollama, cloud APIs, or custom PyTorch models")
    parser.add_argument("--guided-backend", choices=["null", "mock", "serial", "udp"], default=None, help="Optional guided-mode backend override")
    parser.add_argument("--name", default="custom_robot_reference", help="Platform name to place into the generated profile")
    parser.add_argument("--platform-type", default="custom_hardware", help="Platform type identifier for the generated profile")
    parser.add_argument("--backend", choices=["null", "mock", "serial", "udp"], default=None, help="Optional transport backend override")
    parser.add_argument("--stage", default="C", help="Runtime stage for the generated profile")
    parser.add_argument("--action-scheme-name", default=None, help="Optional explicit name for the generated action_scheme block")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it already exists")
    return parser


def scaffold_hardware_profile(
    *,
    output_path: str | Path,
    example: str = "template",
    preset: str = "default",
    guided_goal: str | None = None,
    guided_backend: str | None = None,
    name: str = "custom_robot_reference",
    platform_type: str = "custom_hardware",
    backend: str | None = None,
    stage: str = "C",
    action_scheme_name: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    destination = Path(output_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {destination}")

    resolved = resolve_scaffold_plan(
        guided_goal=guided_goal,
        example=example,
        preset=preset,
        backend=backend,
        guided_backend=guided_backend,
        platform_type=platform_type,
    )
    profile = _load_profile_source(resolved["source"])
    _customize_profile(
        profile,
        name=name,
        platform_type=resolved["platform_type"],
        backend=resolved["backend"],
        stage=stage,
        action_scheme_name=action_scheme_name,
        preset=resolved["preset"],
        source=resolved["source"],
        guided_goal=guided_goal,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    profile = scaffold_hardware_profile(
        output_path=args.output,
        example=args.example,
        preset=args.preset,
        guided_goal=args.guided_goal,
        guided_backend=args.guided_backend,
        name=args.name,
        platform_type=args.platform_type,
        backend=args.backend,
        stage=args.stage,
        action_scheme_name=args.action_scheme_name,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "output": str(Path(args.output)),
                "platform": profile.get("hardware", {}).get("platform", {}),
                "preset": profile.get("scaffold_metadata", {}).get("preset", args.preset),
                "guided_goal": profile.get("scaffold_metadata", {}).get("guided_goal"),
                "source": profile.get("scaffold_metadata", {}).get("source"),
                "action_scheme": profile.get("action_scheme", {}),
            },
            indent=2,
        )
    )


def resolve_scaffold_plan(
    *,
    guided_goal: str | None,
    example: str,
    preset: str,
    backend: str | None,
    guided_backend: str | None,
    platform_type: str,
) -> dict[str, str | None]:
    if guided_goal is None:
        return {
            "source": example,
            "preset": preset,
            "backend": backend,
            "platform_type": platform_type,
        }
    goal_map: dict[str, dict[str, str | None]] = {
        "custom_hardware": {
            "source": "template",
            "preset": "wheeled_arm",
            "backend": guided_backend or backend or "udp",
            "platform_type": platform_type,
        },
        "armsmart_hardware": {
            "source": "armsmart_mock" if (guided_backend or backend or "mock") == "mock" else "armsmart_hil",
            "preset": "default",
            "backend": guided_backend or backend or "mock",
            "platform_type": "armsmart_reference",
        },
        "local_ollama": {
            "source": "examples/inference/armsmart_ollama/profile.json",
            "preset": "default",
            "backend": guided_backend or backend or "mock",
            "platform_type": "armsmart_reference",
        },
        "cloud_api": {
            "source": "examples/inference/armsmart_cloud_api/profile.json",
            "preset": "default",
            "backend": guided_backend or backend or "mock",
            "platform_type": "armsmart_reference",
        },
        "custom_pytorch": {
            "source": "examples/inference/armsmart_pytorch_custom/profile.json",
            "preset": "default",
            "backend": guided_backend or backend or "mock",
            "platform_type": "armsmart_reference",
        },
    }
    return goal_map[guided_goal]


def _load_example_profile(example: str) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    if example == "template":
        source = repo_root / "profiles" / "hardware_template" / "profile.json"
    else:
        source = repo_root / "profiles" / example / "profile.json"
    return json.loads(source.read_text(encoding="utf-8"))


def _load_profile_source(source: str | None) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    if source is None:
        source = "template"
    if source.startswith("examples/"):
        path = repo_root / Path(source)
        return json.loads(path.read_text(encoding="utf-8"))
    return _load_example_profile(source)


def _customize_profile(
    profile: dict[str, Any],
    *,
    name: str,
    platform_type: str,
    backend: str | None,
    stage: str,
    action_scheme_name: str | None,
    preset: str,
    source: str | None,
    guided_goal: str | None,
) -> None:
    hardware = profile.setdefault("hardware", {})
    platform = hardware.setdefault("platform", {})
    platform["name"] = name
    platform["type"] = platform_type
    if platform_type != "armsmart_reference":
        platform["description"] = f"Hardware scaffold for {name} using the {preset} preset."
    connection = hardware.setdefault("connection", {})
    if backend is not None:
        connection["backend"] = backend
    _apply_preset(profile, preset)
    _apply_action_scheme(profile, preset=preset, guided_goal=guided_goal, name=action_scheme_name)
    profile.setdefault("runtime", {})["stage"] = stage
    profile["runtime"]["mode"] = "hardware"
    profile.setdefault("logs", {})["run_dir"] = f"logs/{name}"
    profile["scaffold_metadata"] = {
        "source": source,
        "preset": preset,
        "guided_goal": guided_goal,
    }
    _apply_llm_task_defaults(profile, guided_goal=guided_goal)
    mock_cfg = hardware.get("mock")
    if connection.get("backend") != "mock" and isinstance(mock_cfg, dict):
        mock_cfg.setdefault("active_scenario", "nominal")


def _apply_llm_task_defaults(profile: dict[str, Any], *, guided_goal: str | None) -> None:
    if guided_goal not in {"local_ollama", "cloud_api"}:
        return
    llm_cfg = profile.setdefault("llm", {})
    llm_cfg.setdefault("role_contract_file", "SOUL.md")
    llm_cfg.setdefault(
        "task",
        {
            "name": "user_defined_robot_task",
            "goal": "Set a concrete robot task here, for example: grasp the right object or fold a cloth.",
            "success_criteria": [
                "finish the requested task safely",
                "stay compatible with the configured action scheme and safety workflow",
            ],
            "constraints": [
                "do not bypass the IronEngine-RL safety layer",
                "base reasoning only on available observation and repository context",
            ],
        },
    )
    profile.setdefault("model_provider", {}).setdefault("role_contract_file", llm_cfg["role_contract_file"])


def _apply_action_scheme(profile: dict[str, Any], *, preset: str, guided_goal: str | None, name: str | None) -> None:
    action_scheme = profile.setdefault("action_scheme", {})
    action_scheme["name"] = name or action_scheme.get("name") or _default_action_scheme_name(preset, guided_goal)
    action_scheme["command_channels"] = _infer_action_channels(profile)
    action_scheme["feedback_fields"] = _infer_feedback_fields(profile)
    action_scheme.setdefault("result_fields", ["reward.total", "reward.components", "done", "info.success"])
    action_scheme["schedule_notes"] = _default_schedule_notes(profile, preset=preset, guided_goal=guided_goal)


def _default_action_scheme_name(preset: str, guided_goal: str | None) -> str:
    if guided_goal:
        return f"{guided_goal}_action_scheme"
    return f"{preset}_action_scheme" if preset != "default" else "generated_action_scheme"


def _infer_action_channels(profile: dict[str, Any]) -> list[str]:
    candidates = [
        profile.get("hardware", {}).get("platform", {}).get("capabilities", {}).get("action_channels"),
        profile.get("platform", {}).get("capabilities", {}).get("action_channels"),
        profile.get("agent", {}).get("contract", {}).get("action_channels"),
        profile.get("boundary_conditions", {}).get("contract", {}).get("action_channels"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return list(candidate)
    return list(DEFAULT_ACTION_CHANNELS)


def _infer_feedback_fields(profile: dict[str, Any]) -> list[str]:
    task_contract = profile.get("evaluation", {}).get("task", {})
    if not isinstance(task_contract, dict):
        task_contract = {}
    candidates = [
        profile.get("hardware", {}).get("platform", {}).get("capabilities", {}).get("observation_fields"),
        profile.get("platform", {}).get("capabilities", {}).get("observation_fields"),
        profile.get("model_provider", {}).get("contract", {}).get("observation_fields"),
        task_contract.get("contract", {}).get("observation_fields"),
        profile.get("boundary_conditions", {}).get("contract", {}).get("observation_fields"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return list(candidate)
    return list(DEFAULT_FEEDBACK_FIELDS)


def _default_schedule_notes(profile: dict[str, Any], *, preset: str, guided_goal: str | None) -> list[str]:
    existing = profile.get("action_scheme", {}).get("schedule_notes")
    if isinstance(existing, list) and existing:
        return list(existing)
    channels = _infer_action_channels(profile)
    notes: list[str] = ["validate command-to-feedback flow on mock transport before hardware deployment"]
    if "chassis_forward" in channels and "arm_extend" in channels:
        notes.append("stabilize base motion before aggressive arm extension")
    if "gripper_close" in channels:
        notes.append("close gripper only after alignment and reachability signals are acceptable")
    if preset == "visionless_link_monitor" or guided_goal == "custom_hardware":
        notes.append("treat link-health feedback as a scheduling gate before motion")
    if guided_goal in {"local_ollama", "cloud_api"}:
        notes.append("keep hardware action timing conservative while prompt-driven inference is being validated")
    return notes


def _apply_preset(profile: dict[str, Any], preset: str) -> None:
    if preset == "default":
        return
    if preset == "wheeled_arm":
        _apply_wheeled_arm_preset(profile)
        return
    if preset == "arm_only":
        _apply_arm_only_preset(profile)
        return
    if preset == "visionless_link_monitor":
        _apply_visionless_link_monitor_preset(profile)
        return
    raise ValueError(f"Unsupported preset: {preset}")


def _apply_wheeled_arm_preset(profile: dict[str, Any]) -> None:
    hardware = profile.setdefault("hardware", {})
    capabilities = hardware.setdefault("platform", {}).setdefault("capabilities", {})
    capabilities["camera_roles"] = ["dash", "claw"]
    capabilities["observation_fields"] = [
        "connection_alive",
        "battery_level",
        "collision_risk",
        "object_dx",
        "object_dy",
        "arm_height",
        "arm_extension",
        "claw_alignment",
        "gripper_close",
    ]
    capabilities["action_channels"] = [
        "chassis_forward",
        "chassis_strafe",
        "chassis_turn",
        "arm_lift",
        "arm_extend",
        "wrist_yaw",
        "gripper_close",
    ]
    hardware.setdefault("connection", {}).setdefault("default_mode", "arm")
    profile.setdefault("evaluation", {})["task"] = "tabletop_grasp"
    profile["evaluation"]["metrics"] = ["task_performance", "boundary_violations"]


def _apply_arm_only_preset(profile: dict[str, Any]) -> None:
    hardware = profile.setdefault("hardware", {})
    capabilities = hardware.setdefault("platform", {}).setdefault("capabilities", {})
    capabilities["camera_roles"] = ["claw"]
    capabilities["observation_fields"] = [
        "connection_alive",
        "battery_level",
        "collision_risk",
        "arm_height",
        "arm_extension",
        "claw_alignment",
        "gripper_close",
    ]
    capabilities["action_channels"] = ["arm_lift", "arm_extend", "wrist_yaw", "gripper_close"]
    cameras = hardware.setdefault("cameras", {})
    cameras["backend"] = cameras.get("backend", "placeholder")
    cameras.pop("dash", None)
    cameras.setdefault("claw", {"camera_id": "claw_cam_hw", "device_index": 0, "role": "claw"})
    profile.setdefault("evaluation", {})["task"] = {
        "name": "tabletop_grasp",
        "contract": {
            "camera_roles": ["claw"],
            "observation_fields": ["arm_height", "arm_extension", "claw_alignment"],
        },
    }
    profile["evaluation"]["metrics"] = ["task_performance", "boundary_violations"]


def _apply_visionless_link_monitor_preset(profile: dict[str, Any]) -> None:
    hardware = profile.setdefault("hardware", {})
    capabilities = hardware.setdefault("platform", {}).setdefault("capabilities", {})
    capabilities["camera_roles"] = []
    capabilities["observation_fields"] = [
        "connection_alive",
        "battery_level",
        "collision_risk",
        "arm_height",
        "arm_extension",
        "gripper_close",
    ]
    capabilities["action_channels"] = ["arm_lift", "arm_extend", "gripper_close"]
    cameras = hardware.setdefault("cameras", {})
    cameras["backend"] = "placeholder"
    cameras.pop("dash", None)
    cameras.pop("claw", None)
    profile["model_provider"] = {
        "type": "custom_plugin",
        "plugin": {"module_path": "user_modules.examples.inference.visionless_inference_provider:VisionlessInferenceProvider"},
        "contract": {
            "observation_fields": ["connection_alive", "battery_level", "collision_risk", "arm_height", "arm_extension"],
            "camera_roles": [],
        },
    }
    profile["agent"] = {
        "type": "custom_plugin",
        "plugin": {"module_path": "user_modules.examples.agents.stability_agent:StabilityAgent"},
        "contract": {"action_channels": ["arm_lift", "arm_extend", "gripper_close"]},
    }
    profile["boundary_conditions"] = {
        "type": "custom_plugin",
        "plugin": {"module_path": "user_modules.examples.safety.connection_aware_policy:ConnectionAwareSafetyPolicy"},
        "contract": {
            "observation_fields": ["connection_alive", "battery_level", "collision_risk"],
            "camera_roles": [],
            "action_channels": ["arm_lift", "arm_extend", "gripper_close"],
        },
        "connection_hold_threshold": 0.6,
    }
    profile["evaluation"] = {
        "task": {
            "name": "hardware_link_validation",
            "contract": {
                "observation_fields": ["connection_alive", "battery_level", "collision_risk"],
                "camera_roles": [],
            },
        },
        "metrics": ["boundary_violations"],
    }


if __name__ == "__main__":
    main()
