from __future__ import annotations

from typing import Any


def compute_boundary_conditions(profile: dict[str, Any]) -> dict[str, Any]:
    runtime_cfg = profile.get("runtime", {})
    simulator_cfg = profile.get("simulator", {})
    transport_cfg = profile.get("transport", {})
    safety_cfg = profile.get("safety", {})
    evaluation_cfg = profile.get("evaluation", {})
    return {
        "runtime_mode": runtime_cfg.get("mode", "simulation"),
        "stage": runtime_cfg.get("stage", "A"),
        "action_bounds": {
            "max_chassis_speed": float(safety_cfg.get("max_chassis_speed", 0.8)),
            "max_turn_rate": float(safety_cfg.get("max_turn_rate", 0.7)),
            "max_arm_speed": float(safety_cfg.get("max_arm_speed", 0.8)),
            "max_arm_extension": float(safety_cfg.get("max_arm_extension", 0.85)),
            "max_gripper_close": float(safety_cfg.get("max_gripper_close", 1.0)),
        },
        "safety_thresholds": {
            "collision_stop_threshold": float(safety_cfg.get("collision_stop_threshold", 0.95)),
            "low_battery_stop_threshold": float(safety_cfg.get("low_battery_stop_threshold", 0.15)),
            "stale_observation_stop_steps": int(safety_cfg.get("stale_observation_stop_steps", 3)),
            "connection_required": bool(safety_cfg.get("connection_required", runtime_cfg.get("mode") == "hardware")),
        },
        "timing": {
            "dt_s": float(simulator_cfg.get("dt_s", 0.1)),
            "max_steps": int(simulator_cfg.get("max_steps", 50)),
            "transport_timeout_s": float(transport_cfg.get("timeout_s", 0.05)),
            "read_chunk_size": int(transport_cfg.get("read_chunk_size", 256)),
        },
        "task_success": {
            "signal": evaluation_cfg.get("success_signal", "object_grasped > 0.5"),
            "task_name": evaluation_cfg.get("task", "tabletop_grasp"),
        },
    }
