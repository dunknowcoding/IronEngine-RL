from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from typing import Any

from .protocol_codec import ProtocolParser, encode_frame


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class BaseTransport:
    name = "base"

    def connect(self) -> bool:
        return False

    def send(self, payload: bytes) -> bool:
        return False

    def send_many(self, payloads: list[bytes]) -> bool:
        ok = True
        for payload in payloads:
            ok = self.send(payload) and ok
        return ok

    def receive(self) -> dict[str, Any] | None:
        return None


@dataclass(slots=True)
class NullTransport(BaseTransport):
    profile: dict[str, Any]
    name: str = "null"
    sent_packets: list[bytes] = field(default_factory=list)

    def connect(self) -> bool:
        return False

    def send(self, payload: bytes) -> bool:
        self.sent_packets.append(payload)
        return True


@dataclass(slots=True)
class MockTransport(BaseTransport):
    profile: dict[str, Any]
    name: str = "mock"
    sent_packets: list[bytes] = field(default_factory=list)
    inbound_frames: list[bytes] = field(default_factory=list)
    telemetry_packets: list[dict[str, Any]] = field(default_factory=list)
    parser: ProtocolParser = field(default_factory=ProtocolParser, init=False)
    reactive_state: dict[str, float | str] = field(default_factory=dict)

    def connect(self) -> bool:
        transport_cfg = self.profile.get("transport", {})
        active_scenario = transport_cfg.get("active_scenario")
        scenario_map = transport_cfg.get("mock_scenarios", {})
        self.reactive_state = {
            "mode": "arm",
            "battery_level": 0.95,
            "collision_risk": 0.04,
            "object_grasped": 0.0,
            "imu_roll_deg": 2.5,
            "imu_pitch_deg": -1.0,
            "imu_yaw_deg": 6.0,
            "dash_visibility": 0.74,
            "claw_visibility": 0.33,
            "object_dx": 0.65,
            "object_dy": 0.04,
            "arm_height": 0.2,
            "arm_extension": 0.15,
            "claw_alignment": 0.62,
            "gripper_close": 0.0,
            "chassis_activity": 0.0,
            "timestamp_s": 0.0,
        }
        if active_scenario and active_scenario in scenario_map:
            self.telemetry_packets = [dict(packet) for packet in scenario_map[active_scenario]]
        else:
            self.telemetry_packets = [dict(packet) for packet in transport_cfg.get("mock_packets", [])]
        return True

    def send(self, payload: bytes) -> bool:
        self.sent_packets.append(payload)
        for frame in self.parser.feed(payload):
            self._enqueue_reply(frame.command, frame.payload)
        return True

    def receive(self) -> dict[str, Any] | None:
        if self.inbound_frames:
            data = self.inbound_frames.pop(0)
            frame = ProtocolParser().feed(data)[0]
            return {
                "protocol_command": frame.command,
                "payload_hex": frame.payload.hex(),
                "payload_bytes": frame.payload,
                "timestamp_s": 0.0,
            }
        if self.telemetry_packets:
            return self.telemetry_packets.pop(0)
        return None

    def _enqueue_reply(self, command: int, payload: bytes) -> None:
        commands = self.profile.get("transport", {}).get("protocol_commands", {})
        if command == commands.get("ping", 0x01):
            self.inbound_frames.append(encode_frame(commands.get("pong", 0x02)))
        elif command == commands.get("set_mode_arm", 0x10):
            self.reactive_state["mode"] = "arm"
            self.inbound_frames.append(encode_frame(commands.get("mode_ack", 0x12), bytes([1])))
            self._maybe_append_reactive_telemetry()
        elif command == commands.get("set_mode_car", 0x11):
            self.reactive_state["mode"] = "car"
            self.inbound_frames.append(encode_frame(commands.get("mode_ack", 0x12), bytes([2])))
            self._maybe_append_reactive_telemetry()
        elif command == commands.get("servo_name_get", 0x42) and payload:
            servo_id = payload[0]
            servo_name = f"servo_{servo_id}".encode("utf-8")
            self.inbound_frames.append(encode_frame(commands.get("servo_name_reply", 0x43), bytes([servo_id]) + servo_name))
        elif command == commands.get("motor_set", 0x30) and len(payload) >= 8:
            wheel_values = [int.from_bytes(payload[index : index + 2], byteorder="little", signed=True) for index in range(0, 8, 2)]
            self._apply_motor_activity(wheel_values)
            self._maybe_append_reactive_telemetry()
        elif command == commands.get("servo_set", 0x20) and len(payload) >= 3:
            servo_id = payload[0]
            angle = int.from_bytes(payload[1:3], byteorder="little", signed=False)
            self._apply_servo_activity(servo_id, angle)
            self._maybe_append_reactive_telemetry()

    def _apply_motor_activity(self, wheel_values: list[int]) -> None:
        avg_activity = sum(abs(value) for value in wheel_values) / (4 * 255)
        self.reactive_state["chassis_activity"] = avg_activity
        self.reactive_state["collision_risk"] = _clamp(0.05 + avg_activity * 0.35, 0.0, 1.0)
        self.reactive_state["imu_roll_deg"] = float(self.reactive_state["imu_roll_deg"]) + avg_activity * 1.5
        self.reactive_state["imu_yaw_deg"] = float(self.reactive_state["imu_yaw_deg"]) + avg_activity * 2.5
        self.reactive_state["dash_visibility"] = _clamp(float(self.reactive_state["dash_visibility"]) - avg_activity * 0.08, 0.2, 1.0)
        self.reactive_state["battery_level"] = _clamp(float(self.reactive_state["battery_level"]) - avg_activity * 0.015, 0.0, 1.0)
        self.reactive_state["object_dx"] = _clamp(float(self.reactive_state["object_dx"]) - avg_activity * 0.18, 0.05, 1.0)
        self.reactive_state["claw_alignment"] = _clamp(float(self.reactive_state["claw_alignment"]) + avg_activity * 0.08, 0.0, 1.0)

    def _apply_servo_activity(self, servo_id: int, angle: int) -> None:
        normalized = angle / 180.0
        if servo_id == 1:
            self.reactive_state["arm_height"] = normalized * 0.45
        if servo_id == 2:
            self.reactive_state["arm_extension"] = normalized
            self.reactive_state["claw_visibility"] = _clamp(0.25 + normalized * 0.7, 0.0, 1.0)
            self.reactive_state["object_dx"] = _clamp(0.72 - normalized * 0.7, 0.02, 1.0)
            self.reactive_state["claw_alignment"] = _clamp(0.55 + normalized * 0.4, 0.0, 1.0)
        elif servo_id == 4:
            gripper_close = _clamp((angle - 20) / 70.0, 0.0, 1.0)
            self.reactive_state["gripper_close"] = gripper_close
            if float(self.reactive_state["arm_extension"]) > 0.55 and gripper_close > 0.65:
                self.reactive_state["object_grasped"] = 1.0
                self.reactive_state["claw_visibility"] = _clamp(float(self.reactive_state["claw_visibility"]) + 0.15, 0.0, 1.0)
                self.reactive_state["object_dx"] = 0.04
                self.reactive_state["claw_alignment"] = 0.96
        self.reactive_state["battery_level"] = _clamp(float(self.reactive_state["battery_level"]) - 0.004, 0.0, 1.0)

    def _maybe_append_reactive_telemetry(self) -> None:
        transport_cfg = self.profile.get("transport", {})
        if transport_cfg.get("active_scenario") != "reactive_grasp":
            return
        self.reactive_state["timestamp_s"] = float(self.reactive_state["timestamp_s"]) + 0.1
        packet = {
            "timestamp_s": float(self.reactive_state["timestamp_s"]),
            "connection_alive": 1.0,
            "battery_level": float(self.reactive_state["battery_level"]),
            "collision_risk": float(self.reactive_state["collision_risk"]),
            "object_grasped": float(self.reactive_state["object_grasped"]),
            "object_dx": float(self.reactive_state["object_dx"]),
            "object_dy": 0.04,
            "imu_roll_deg": float(self.reactive_state["imu_roll_deg"]),
            "imu_pitch_deg": float(self.reactive_state["imu_pitch_deg"]),
            "imu_yaw_deg": float(self.reactive_state["imu_yaw_deg"]),
            "arm_height": float(self.reactive_state["arm_height"]),
            "arm_extension": float(self.reactive_state["arm_extension"]),
            "claw_alignment": float(self.reactive_state["claw_alignment"]),
            "dash_visibility": float(self.reactive_state["dash_visibility"]),
            "claw_visibility": float(self.reactive_state["claw_visibility"]),
        }
        self.telemetry_packets.append(packet)


@dataclass(slots=True)
class SerialTransport(BaseTransport):
    profile: dict[str, Any]
    name: str = "serial"
    serial_handle: Any = field(default=None, init=False)
    parser: ProtocolParser = field(default_factory=ProtocolParser, init=False)

    def connect(self) -> bool:
        transport = self.profile.get("transport", {})
        try:
            import serial  # type: ignore
        except Exception:
            return False
        try:
            self.serial_handle = serial.Serial(
                port=transport.get("serial_port", "COM5"),
                baudrate=int(transport.get("baud_rate", 115200)),
                timeout=float(transport.get("timeout_s", 0.05)),
            )
        except Exception:
            self.serial_handle = None
        return self.serial_handle is not None

    def send(self, payload: bytes) -> bool:
        if self.serial_handle is None:
            return False
        self.serial_handle.write(payload)
        return True

    def receive(self) -> dict[str, Any] | None:
        if self.serial_handle is None:
            return None
        size = int(self.profile.get("transport", {}).get("read_chunk_size", 256))
        data = self.serial_handle.read(size)
        if not data:
            return None
        frames = self.parser.feed(data)
        if not frames:
            return None
        frame = frames[0]
        return {
            "protocol_command": frame.command,
            "payload_hex": frame.payload.hex(),
            "payload_bytes": frame.payload,
        }


@dataclass(slots=True)
class UdpTransport(BaseTransport):
    profile: dict[str, Any]
    name: str = "udp"
    socket_handle: socket.socket | None = field(default=None, init=False)
    parser: ProtocolParser = field(default_factory=ProtocolParser, init=False)

    def connect(self) -> bool:
        transport = self.profile.get("transport", {})
        udp_cfg = transport.get("udp", {})
        host = udp_cfg.get("host")
        port = udp_cfg.get("port")
        if not host or not port:
            return False
        try:
            self.socket_handle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket_handle.settimeout(float(udp_cfg.get("timeout_s", 0.05)))
            return True
        except OSError:
            self.socket_handle = None
            return False

    def send(self, payload: bytes) -> bool:
        if self.socket_handle is None:
            return False
        udp_cfg = self.profile.get("transport", {}).get("udp", {})
        self.socket_handle.sendto(payload, (udp_cfg["host"], int(udp_cfg["port"])))
        return True

    def receive(self) -> dict[str, Any] | None:
        if self.socket_handle is None:
            return None
        try:
            data, _ = self.socket_handle.recvfrom(4096)
        except OSError:
            return None
        frames = self.parser.feed(data)
        if frames:
            frame = frames[0]
            return {
                "protocol_command": frame.command,
                "payload_hex": frame.payload.hex(),
                "payload_bytes": frame.payload,
            }
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None


def transport_from_profile(profile: dict[str, Any]) -> BaseTransport:
    transport_cfg = profile.get("transport", {})
    backend = transport_cfg.get("backend", "null")
    if backend == "mock":
        return MockTransport(profile)
    if backend == "serial":
        return SerialTransport(profile)
    if backend == "udp":
        return UdpTransport(profile)
    return NullTransport(profile)