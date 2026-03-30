from __future__ import annotations

from collections import deque
import math
import random
from dataclasses import asdict, dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, EnvironmentPort, Observation, RewardBreakdown, StepResult
from ironengine_rl.vision import simulation_camera_rig_from_profile


@dataclass(slots=True)
class WorldState:
    time_s: float = 0.0
    robot_x: float = 0.0
    robot_y: float = 0.0
    robot_heading_deg: float = 0.0
    arm_height: float = 0.25
    arm_extension: float = 0.2
    wrist_yaw_deg: float = 0.0
    gripper_close: float = 0.0
    object_x: float = 1.4
    object_y: float = 0.35
    object_grasped: float = 0.0
    battery_level: float = 1.0


@dataclass(slots=True)
class FaultModel:
    sensor_dropout_probability: float = 0.0
    camera_dropout_probability: float = 0.0
    action_lag_steps: int = 0
    observation_delay_steps: int = 0
    collision_bias: float = 0.0
    object_sensor_bias_x: float = 0.0
    object_sensor_bias_y: float = 0.0
    battery_drain_scale: float = 1.0
    wrist_drift_deg: float = 0.0
    intermittent_fault_after_step: int = 0


class DeterministicARMSmartEnv(EnvironmentPort):
    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        simulator_cfg = profile.get("simulator", {})
        self.dt_s = float(simulator_cfg.get("dt_s", 0.1))
        self.max_steps = int(simulator_cfg.get("max_steps", 50))
        self.enable_noise = bool(simulator_cfg.get("enable_noise", False))
        self.camera_rig = simulation_camera_rig_from_profile(profile)
        self.reward_cfg = profile.get("reward", {})
        fault_cfg = simulator_cfg.get("faults", {})
        self.fault_model = FaultModel(
            sensor_dropout_probability=float(fault_cfg.get("sensor_dropout_probability", 0.0)),
            camera_dropout_probability=float(fault_cfg.get("camera_dropout_probability", 0.0)),
            action_lag_steps=int(fault_cfg.get("action_lag_steps", 0)),
            observation_delay_steps=int(fault_cfg.get("observation_delay_steps", 0)),
            collision_bias=float(fault_cfg.get("collision_bias", 0.0)),
            object_sensor_bias_x=float(fault_cfg.get("object_sensor_bias_x", 0.0)),
            object_sensor_bias_y=float(fault_cfg.get("object_sensor_bias_y", 0.0)),
            battery_drain_scale=float(fault_cfg.get("battery_drain_scale", 1.0)),
            wrist_drift_deg=float(fault_cfg.get("wrist_drift_deg", 0.0)),
            intermittent_fault_after_step=int(fault_cfg.get("intermittent_fault_after_step", 0)),
        )
        self.reset()

    def reset(self) -> Observation:
        self.steps_taken = 0
        self.state = WorldState()
        self._reset_scene()
        self.last_distance = self._object_distance()
        self.pending_actions: deque[ActionCommand] = deque()
        self.observation_history: deque[Observation] = deque()
        initial_observation = self._observe()
        self.observation_history.append(initial_observation)
        return initial_observation

    def step(self, action: ActionCommand) -> StepResult:
        self.steps_taken += 1
        effective_action = self._resolve_action(action)
        self._apply_action(effective_action)
        observation = self._observe()
        served_observation = self._resolve_observation(observation)
        reward = self._reward(effective_action, served_observation)
        done = bool(observation.sensors.get("object_grasped", 0.0) > 0.5 or self.steps_taken >= self.max_steps)
        anomalies = self._anomaly_flags(served_observation)
        info = {
            "step": self.steps_taken,
            "success": bool(observation.sensors.get("object_grasped", 0.0) > 0.5),
            "phase_hint": "grasp" if observation.sensors.get("claw_alignment", 0.0) > 0.85 else "approach",
            "effective_action": asdict(effective_action),
            "anomalies": anomalies,
        }
        return StepResult(observation=served_observation, reward=reward, done=done, info=info)

    def _apply_action(self, action: ActionCommand) -> None:
        self.state.time_s += self.dt_s
        self.state.robot_heading_deg = self._wrap_deg(self.state.robot_heading_deg + action.chassis_turn * 18.0 * self.dt_s)
        heading_rad = math.radians(self.state.robot_heading_deg)
        forward_scale = 0.35
        strafe_scale = 0.25
        self.state.robot_x += (math.cos(heading_rad) * action.chassis_forward - math.sin(heading_rad) * action.chassis_strafe) * forward_scale * self.dt_s
        self.state.robot_y += (math.sin(heading_rad) * action.chassis_forward + math.cos(heading_rad) * action.chassis_strafe) * strafe_scale * self.dt_s
        self.state.arm_height = self._clamp(self.state.arm_height + action.arm_lift * 0.12 * self.dt_s, 0.05, 0.55)
        self.state.arm_extension = self._clamp(self.state.arm_extension + action.arm_extend * 0.18 * self.dt_s, 0.05, 0.85)
        drift = self.fault_model.wrist_drift_deg if self._fault_window_active() else 0.0
        self.state.wrist_yaw_deg = self._clamp(self.state.wrist_yaw_deg + action.wrist_yaw * 20.0 * self.dt_s + drift, -85.0, 85.0)
        self.state.gripper_close = self._clamp(self.state.gripper_close + action.gripper_close * 0.25 * self.dt_s, 0.0, 1.0)
        motion_load = sum(abs(value) for value in [action.chassis_forward, action.chassis_strafe, action.chassis_turn, action.arm_lift, action.arm_extend, action.wrist_yaw, action.gripper_close])
        self.state.battery_level = self._clamp(self.state.battery_level - 0.0008 * motion_load * self.fault_model.battery_drain_scale, 0.0, 1.0)
        if self._grasp_condition_met():
            self.state.object_grasped = 1.0
            self.state.object_x = self.state.robot_x + math.cos(heading_rad) * self.state.arm_extension
            self.state.object_y = self.state.robot_y + math.sin(heading_rad) * self.state.arm_extension

    def _observe(self) -> Observation:
        object_dx = self.state.object_x - self.state.robot_x
        object_dy = self.state.object_y - self.state.robot_y
        heading_error_deg = self._wrap_deg(math.degrees(math.atan2(object_dy, object_dx)) - self.state.robot_heading_deg)
        object_distance = (object_dx**2 + object_dy**2) ** 0.5
        claw_x = self.state.robot_x + math.cos(math.radians(self.state.robot_heading_deg)) * self.state.arm_extension
        claw_y = self.state.robot_y + math.sin(math.radians(self.state.robot_heading_deg)) * self.state.arm_extension
        claw_distance = ((self.state.object_x - claw_x) ** 2 + (self.state.object_y - claw_y) ** 2) ** 0.5
        claw_alignment = max(0.0, 1.0 - abs(heading_error_deg) / 80.0)
        collision_risk = 1.0 if abs(self.state.robot_x) > 2.0 or abs(self.state.robot_y) > 2.0 else 0.0
        collision_risk = self._clamp(collision_risk + self.fault_model.collision_bias, 0.0, 1.0)
        object_height_target = float(self.profile.get("simulator", {}).get("grasp_height_target", 0.18))
        vertical_error = abs(self.state.arm_height - object_height_target)
        pregrasp_ready = 1.0 if claw_distance < 0.18 and claw_alignment > 0.82 and vertical_error < 0.08 else 0.0
        target_reachable = 1.0 if object_distance < 1.1 else 0.0
        scene_detections = self._scene_detections()
        world_features = {
            "object_distance": object_distance,
            "heading_error_deg": heading_error_deg,
            "claw_distance": claw_distance,
            "claw_alignment": claw_alignment,
            "pregrasp_ready": pregrasp_ready,
            "target_reachable": target_reachable,
            "target_object_label": self.target_object_label,
            "scene_detections": scene_detections,
        }
        cameras = self.camera_rig.capture(self.state.time_s, world_features)
        cameras = self._apply_camera_faults(cameras)
        sensors = {
            "object_dx": self._noise(object_dx + self.fault_model.object_sensor_bias_x, 0.01),
            "object_dy": self._noise(object_dy + self.fault_model.object_sensor_bias_y, 0.01),
            "object_distance": self._noise(object_distance, 0.01),
            "heading_error_deg": self._noise(heading_error_deg, 0.5),
            "arm_height": self._noise(self.state.arm_height, 0.005),
            "arm_extension": self._noise(self.state.arm_extension, 0.005),
            "wrist_yaw_deg": self._noise(self.state.wrist_yaw_deg, 0.5),
            "gripper_close": self._noise(self.state.gripper_close, 0.01),
            "claw_distance": self._noise(claw_distance, 0.01),
            "claw_alignment": self._noise(claw_alignment, 0.02),
            "vertical_error": self._noise(vertical_error, 0.01),
            "pregrasp_ready": pregrasp_ready,
            "target_reachable": target_reachable,
            "scene_object_count": float(len(self.scene_objects)),
            "distractor_count": float(max(0, len(self.scene_objects) - 1)),
            "target_object_visible": 1.0 if any(detection.get("is_target") and detection.get("confidence", 0.0) > 0.35 for detection in scene_detections) else 0.0,
            "collision_risk": collision_risk,
            "battery_level": self.state.battery_level,
            "object_grasped": self.state.object_grasped,
        }
        sensors = self._apply_sensor_faults(sensors)
        return Observation(
            timestamp_s=self.state.time_s,
            sensors=sensors,
            cameras=cameras,
            metadata={
                "stage": self.profile.get("runtime", {}).get("stage", "A"),
                "source": "simulator",
                "future_components": self.profile.get("future_components", []),
                "fault_window_active": self._fault_window_active(),
                "target_object_label": self.target_object_label,
                "scene_objects": [dict(item) for item in self.scene_objects],
            },
        )

    def _reset_scene(self) -> None:
        simulator_cfg = self.profile.get("simulator", {})
        configured_objects = simulator_cfg.get("scene_objects") or []
        if configured_objects:
            self.scene_objects = [
                {
                    "label": str(item.get("label", f"object_{index}")),
                    "x": float(item.get("x", 1.4)),
                    "y": float(item.get("y", 0.35)),
                    "kind": str(item.get("kind", "generic")),
                    "target": bool(item.get("target", False)),
                }
                for index, item in enumerate(configured_objects)
            ]
            explicit_target = str(simulator_cfg.get("target_object_label", "")).strip()
            if explicit_target:
                self.target_object_label = explicit_target
            else:
                target_entry = next((item for item in self.scene_objects if item.get("target")), self.scene_objects[0])
                self.target_object_label = str(target_entry["label"])
            target_object = next((item for item in self.scene_objects if item.get("label") == self.target_object_label), self.scene_objects[0])
            self.state.object_x = float(target_object["x"])
            self.state.object_y = float(target_object["y"])
            return
        object_cfg = simulator_cfg.get("object_pose", {"x": 1.4, "y": 0.35})
        self.target_object_label = str(simulator_cfg.get("target_object_label", "target_object"))
        self.scene_objects = [
            {
                "label": self.target_object_label,
                "x": float(object_cfg.get("x", 1.4)),
                "y": float(object_cfg.get("y", 0.35)),
                "kind": "generic",
                "target": True,
            }
        ]
        self.state.object_x = float(object_cfg.get("x", 1.4))
        self.state.object_y = float(object_cfg.get("y", 0.35))

    def _scene_detections(self) -> list[dict[str, Any]]:
        detections: list[dict[str, Any]] = []
        for item in self.scene_objects:
            dx = float(item.get("x", 0.0)) - self.state.robot_x
            dy = float(item.get("y", 0.0)) - self.state.robot_y
            distance = (dx**2 + dy**2) ** 0.5
            confidence = max(0.0, 1.0 - distance / 3.2)
            detections.append(
                {
                    "label": str(item.get("label", "object")),
                    "kind": str(item.get("kind", "generic")),
                    "confidence": confidence,
                    "is_target": bool(str(item.get("label", "")) == self.target_object_label),
                    "right_side": 1.0 if float(item.get("y", 0.0)) >= 0.0 else 0.0,
                }
            )
        return detections

    def _reward(self, action: ActionCommand, observation: Observation) -> RewardBreakdown:
        distance = observation.sensors["object_distance"]
        progress = self.last_distance - distance
        self.last_distance = distance
        components = {
            "progress": self.reward_cfg.get("progress_scale", 4.0) * progress,
            "alignment": self.reward_cfg.get("alignment_scale", 1.5) * observation.sensors["claw_alignment"],
            "pregrasp": self.reward_cfg.get("pregrasp_scale", 1.2) * observation.sensors.get("pregrasp_ready", 0.0),
            "reachability": self.reward_cfg.get("reachability_scale", 0.6) * observation.sensors.get("target_reachable", 0.0),
            "visibility": self.reward_cfg.get("visibility_scale", 0.5) * sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras),
            "energy": -self.reward_cfg.get("energy_scale", 0.1) * sum(abs(value) for value in [action.chassis_forward, action.chassis_strafe, action.chassis_turn, action.arm_lift, action.arm_extend, action.wrist_yaw, action.gripper_close]),
            "battery_margin": self.reward_cfg.get("battery_margin_scale", 0.2) * observation.sensors.get("battery_level", 1.0),
            "safety": -self.reward_cfg.get("safety_scale", 2.0) * observation.sensors["collision_risk"],
            "vertical_error": -self.reward_cfg.get("vertical_error_scale", 0.8) * observation.sensors.get("vertical_error", 0.0),
            "success": self.reward_cfg.get("success_bonus", 12.0) if observation.sensors["object_grasped"] > 0.5 else 0.0,
        }
        total = sum(components.values())
        return RewardBreakdown(total=total, components=components)

    def _grasp_condition_met(self) -> bool:
        object_dx = self.state.object_x - self.state.robot_x
        object_dy = self.state.object_y - self.state.robot_y
        heading_error_deg = abs(self._wrap_deg(math.degrees(math.atan2(object_dy, object_dx)) - self.state.robot_heading_deg))
        claw_x = self.state.robot_x + math.cos(math.radians(self.state.robot_heading_deg)) * self.state.arm_extension
        claw_y = self.state.robot_y + math.sin(math.radians(self.state.robot_heading_deg)) * self.state.arm_extension
        claw_distance = ((self.state.object_x - claw_x) ** 2 + (self.state.object_y - claw_y) ** 2) ** 0.5
        return bool(claw_distance < 0.12 and heading_error_deg < 12.0 and self.state.gripper_close > 0.65)

    def _object_distance(self) -> float:
        return ((self.state.object_x - self.state.robot_x) ** 2 + (self.state.object_y - self.state.robot_y) ** 2) ** 0.5

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _wrap_deg(value: float) -> float:
        while value > 180.0:
            value -= 360.0
        while value < -180.0:
            value += 360.0
        return value

    def _noise(self, value: float, scale: float) -> float:
        if not self.enable_noise:
            return value
        return value + random.uniform(-scale, scale)

    def _resolve_action(self, action: ActionCommand) -> ActionCommand:
        self.pending_actions.append(action)
        lag_steps = max(0, self.fault_model.action_lag_steps)
        while len(self.pending_actions) <= lag_steps:
            self.pending_actions.append(ActionCommand())
        return self.pending_actions.popleft()

    def _resolve_observation(self, observation: Observation) -> Observation:
        self.observation_history.append(observation)
        delay_steps = max(0, self.fault_model.observation_delay_steps)
        while len(self.observation_history) <= delay_steps:
            self.observation_history.append(observation)
        return self.observation_history.popleft()

    def _apply_sensor_faults(self, sensors: dict[str, float]) -> dict[str, float]:
        if self.fault_model.sensor_dropout_probability <= 0.0:
            return sensors
        faulted = dict(sensors)
        for key, value in list(faulted.items()):
            if key in {"collision_risk", "battery_level", "object_grasped"}:
                continue
            if random.random() < self.fault_model.sensor_dropout_probability:
                faulted[key] = 0.0 if isinstance(value, float) else value
        return faulted

    def _apply_camera_faults(self, cameras: list[Any]) -> list[Any]:
        if self.fault_model.camera_dropout_probability <= 0.0:
            return cameras
        filtered = []
        for camera in cameras:
            if random.random() < self.fault_model.camera_dropout_probability:
                continue
            filtered.append(camera)
        return filtered or cameras[:1]

    def _fault_window_active(self) -> bool:
        start = self.fault_model.intermittent_fault_after_step
        return bool(start and self.steps_taken >= start)

    def _anomaly_flags(self, observation: Observation) -> list[str]:
        anomalies: list[str] = []
        if observation.sensors.get("battery_level", 1.0) < 0.2:
            anomalies.append("low_battery")
        if observation.sensors.get("collision_risk", 0.0) > 0.8:
            anomalies.append("collision_risk")
        if len(observation.cameras) < 2:
            anomalies.append("camera_dropout")
        if self._fault_window_active():
            anomalies.append("fault_window_active")
        return anomalies
