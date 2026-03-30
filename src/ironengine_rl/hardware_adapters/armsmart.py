from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.hardware_adapters.protocol_codec import encode_frame
from ironengine_rl.hardware_adapters.transports import NullTransport, transport_from_profile
from ironengine_rl.interfaces import ActionCommand, CameraFrame, EnvironmentPort, Observation, RewardBreakdown, StepResult
from ironengine_rl.vision import camera_rig_from_profile


@dataclass(slots=True)
class ARMSmartHardwareAdapter(EnvironmentPort):
    profile: dict[str, Any]
    last_command: bytes = field(default=b"", init=False)
    last_packets: list[bytes] = field(default_factory=list, init=False)
    transport_state: dict[str, Any] = field(default_factory=dict, init=False)
    transport: Any = field(default=None, init=False)
    camera_rig: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        transport = self.profile.get("transport", {})
        self.transport_state = {
            "serial_port": transport.get("serial_port", "COM5"),
            "baud_rate": int(transport.get("baud_rate", 115200)),
            "ble_enabled": bool(transport.get("ble_enabled", True)),
            "protocol_commands": transport.get("protocol_commands", {}),
            "connected": False,
            "sequence": 0,
        }
        self.transport = transport_from_profile(self.profile)
        self.camera_rig = camera_rig_from_profile(self.profile)

    def reset(self) -> Observation:
        self.transport_state["connected"] = self.transport.connect()
        self.transport_state["sequence"] = 0
        return self._shape_observation(
            sensors={
                "connection_alive": 1.0 if self.transport_state["connected"] else 0.0,
                "battery_level": 1.0,
                "collision_risk": 0.0,
                "object_grasped": 0.0,
                "gripper_close": 0.0,
            },
            cameras=self.camera_rig.capture(0.0),
            metadata={
                "source": "hardware_placeholder",
                "status": "connected" if self.transport_state["connected"] else "disconnected",
                "transport_backend": getattr(self.transport, "name", "unknown"),
                "next_step": "Attach serial/BLE packet polling and camera backends in this adapter.",
            },
        )

    def step(self, action: ActionCommand) -> StepResult:
        self.last_packets = self.encode_action_packets(action)
        self.last_command = b"".join(self.last_packets)
        self.transport_state["sequence"] += 1
        sent = self.transport.send_many(self.last_packets)
        packet = self.transport.receive()
        if packet:
            observation = self.decode_sensor_packet(packet)
            observation.metadata["encoded_command_hex"] = self.last_command.hex()
            observation.metadata["transport_backend"] = getattr(self.transport, "name", "unknown")
            return StepResult(
                observation=observation,
                reward=RewardBreakdown(total=0.0, components={"hardware_pending": 0.0}),
                done=False,
                info={
                    "encoded_command_hex": self.last_command.hex(),
                    "transport_state": dict(self.transport_state),
                    "transport_sent": sent,
                },
            )
        observation = self._shape_observation(
            sensors={
                "connection_alive": 1.0 if self.transport_state["connected"] else 0.0,
                "battery_level": 1.0,
                "collision_risk": 0.0,
                "object_grasped": 0.0,
                "gripper_close": 0.0,
            },
            cameras=self.camera_rig.capture(float(self.transport_state["sequence"])),
            metadata={
                "source": "hardware_placeholder",
                "status": "command_buffered",
                "encoded_command_hex": self.last_command.hex(),
                "sequence": self.transport_state["sequence"],
                "transport_backend": getattr(self.transport, "name", "unknown"),
            },
        )
        return StepResult(
            observation=observation,
            reward=RewardBreakdown(total=0.0, components={"hardware_pending": 0.0}),
            done=False,
            info={
                "encoded_command_hex": self.last_command.hex(),
                "transport_state": dict(self.transport_state),
                "transport_sent": sent,
            },
        )

    def encode_action(self, action: ActionCommand) -> bytes:
        return b"".join(self.encode_action_packets(action))

    def encode_ping_packet(self) -> bytes:
        commands = self.transport_state["protocol_commands"]
        return encode_frame(commands.get("ping", 0x01))

    def encode_mode_packet(self, mode: str) -> bytes:
        commands = self.transport_state["protocol_commands"]
        command = commands.get("set_mode_arm", 0x10) if mode == "arm" else commands.get("set_mode_car", 0x11)
        return encode_frame(command)

    def encode_servo_name_get_packet(self, servo_id: int) -> bytes:
        commands = self.transport_state["protocol_commands"]
        return encode_frame(commands.get("servo_name_get", 0x42), bytes([servo_id & 0xFF]))

    def encode_action_packets(self, action: ActionCommand) -> list[bytes]:
        commands = self.transport_state["protocol_commands"]
        mode_command = commands.get("set_mode_arm", 0x10)
        motor_command = commands.get("motor_set", 0x30)
        servo_command = commands.get("servo_set", 0x20)
        mode = self.profile.get("transport", {}).get("default_mode", "arm")
        motor_values = self._motor_targets(action)
        servo_values = self._servo_targets(action)
        packets: list[bytes] = []
        packets.append(encode_frame(mode_command if mode == "arm" else commands.get("set_mode_car", 0x11)))
        motor_payload = bytearray()
        for value in motor_values:
            motor_payload.extend(int(value).to_bytes(2, byteorder="little", signed=True))
        packets.append(encode_frame(motor_command, bytes(motor_payload)))
        for servo_id, angle in servo_values:
            servo_payload = bytearray()
            servo_payload.extend(bytes([servo_id]))
            servo_payload.extend(int(angle).to_bytes(2, byteorder="little", signed=False))
            packets.append(encode_frame(servo_command, bytes(servo_payload)))
        return packets

    def decode_sensor_packet(self, packet: dict[str, Any]) -> Observation:
        command = int(packet.get("protocol_command", -1))
        payload_bytes = packet.get("payload_bytes", b"")
        command_map = self.transport_state["protocol_commands"]
        sensors = {
            "connection_alive": float(packet.get("connection_alive", 1.0)),
            "battery_level": float(packet.get("battery_level", 1.0)),
            "collision_risk": float(packet.get("collision_risk", 0.0)),
            "object_grasped": float(packet.get("object_grasped", 0.0)),
            "object_dx": float(packet.get("object_dx", 0.0)),
            "object_dy": float(packet.get("object_dy", 0.0)),
            "imu_roll_deg": float(packet.get("imu_roll_deg", 0.0)),
            "imu_pitch_deg": float(packet.get("imu_pitch_deg", 0.0)),
            "imu_yaw_deg": float(packet.get("imu_yaw_deg", 0.0)),
            "arm_height": float(packet.get("arm_height", 0.0)),
            "arm_extension": float(packet.get("arm_extension", 0.0)),
            "claw_alignment": float(packet.get("claw_alignment", 0.0)),
            "gripper_close": float(packet.get("gripper_close", 0.0)),
            "heartbeat_ok": 0.0,
        }
        metadata = {
            "source": "hardware_packet",
            "timestamp_s": float(packet.get("timestamp_s", 0.0)),
            "protocol_command": command,
            "raw_keys": sorted(packet.keys()),
            "decoded_event": "unknown",
        }
        if command < 0 and any(key in packet for key in ("imu_roll_deg", "imu_pitch_deg", "imu_yaw_deg", "dash_visibility", "claw_visibility")):
            metadata["decoded_event"] = "telemetry_snapshot"
        if command == command_map.get("pong", 0x02):
            sensors["heartbeat_ok"] = 1.0
            metadata["decoded_event"] = "pong"
        if command == command_map.get("mode_ack", 0x12) and payload_bytes:
            sensors["pc_mode"] = float(payload_bytes[0])
            metadata["decoded_event"] = "mode_ack"
            metadata["pc_mode_name"] = self._pc_mode_name(int(payload_bytes[0]))
        if command == command_map.get("servo_name_reply", 0x43) and payload_bytes:
            servo_id = int(payload_bytes[0])
            try:
                servo_name = payload_bytes[1:].decode("utf-8") if len(payload_bytes) > 1 else ""
            except UnicodeDecodeError:
                servo_name = payload_bytes[1:].decode("utf-8", errors="replace") if len(payload_bytes) > 1 else ""
            sensors[f"servo_{servo_id}_known"] = 1.0
            metadata["decoded_event"] = "servo_name_reply"
            metadata["servo_name_reply"] = {"servo_id": servo_id, "servo_name": servo_name}
        cameras = self._camera_frames_from_packet(packet)
        return self._shape_observation(sensors=sensors, cameras=cameras, metadata=metadata)

    def _camera_frames_from_packet(self, packet: dict[str, Any]) -> list[CameraFrame]:
        timestamp_s = float(packet.get("timestamp_s", 0.0))
        return self.camera_rig.capture(timestamp_s, packet)

    def _shape_observation(self, sensors: dict[str, float], cameras: list[CameraFrame], metadata: dict[str, Any]) -> Observation:
        return Observation(
            timestamp_s=float(metadata.get("timestamp_s", 0.0)),
            sensors=sensors,
            cameras=cameras,
            metadata={
                "stage": self.profile.get("runtime", {}).get("stage", "C"),
                "future_components": self.profile.get("future_components", []),
                **metadata,
            },
        )

    @staticmethod
    def summarize_observation(observation: Observation) -> dict[str, Any]:
        return {
            "decoded_event": observation.metadata.get("decoded_event", "unknown"),
            "protocol_command": observation.metadata.get("protocol_command", -1),
            "pc_mode_name": observation.metadata.get("pc_mode_name"),
            "servo_name_reply": observation.metadata.get("servo_name_reply"),
            "heartbeat_ok": observation.sensors.get("heartbeat_ok", 0.0),
            "battery_level": observation.sensors.get("battery_level"),
            "collision_risk": observation.sensors.get("collision_risk"),
            "object_grasped": observation.sensors.get("object_grasped"),
            "object_dx": observation.sensors.get("object_dx"),
            "claw_alignment": observation.sensors.get("claw_alignment"),
            "imu_roll_deg": observation.sensors.get("imu_roll_deg"),
            "dash_visibility": next((camera.features.get("target_visibility") for camera in observation.cameras if camera.role == "dash"), None),
        }

    @staticmethod
    def _pc_mode_name(mode_value: int) -> str:
        return {0: "idle", 1: "arm", 2: "car"}.get(mode_value, f"unknown_{mode_value}")

    @staticmethod
    def _motor_targets(action: ActionCommand) -> tuple[int, int, int, int]:
        forward = action.chassis_forward
        strafe = action.chassis_strafe
        turn = action.chassis_turn
        scale = 255
        front_left = max(-255, min(255, int((forward + strafe + turn) * scale)))
        front_right = max(-255, min(255, int((forward - strafe - turn) * scale)))
        rear_left = max(-255, min(255, int((forward - strafe + turn) * scale)))
        rear_right = max(-255, min(255, int((forward + strafe - turn) * scale)))
        return front_left, front_right, rear_left, rear_right

    @staticmethod
    def _servo_targets(action: ActionCommand) -> tuple[tuple[int, int], ...]:
        def to_angle(value: float, center: int = 90, amplitude: int = 65) -> int:
            return max(0, min(180, int(center + value * amplitude)))

        return (
            (1, to_angle(action.arm_lift)),
            (2, to_angle(action.arm_extend)),
            (3, to_angle(action.wrist_yaw)),
            (4, to_angle(action.gripper_close, center=20, amplitude=70)),
        )
