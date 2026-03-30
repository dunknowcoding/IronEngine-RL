from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from ironengine_rl.config import load_profile
from ironengine_rl.hardware_adapters import ARMSmartHardwareAdapter, encode_frame, transport_from_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose ARMSmart transport and protocol connectivity")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    parser.add_argument("--mode", choices=["arm", "car", "none"], default="arm", help="Optional mode command to send")
    parser.add_argument("--ping", action="store_true", help="Send a ping frame before listening")
    parser.add_argument("--servo-name-id", type=int, action="append", default=[], help="Optional servo ID to query by name; can be provided multiple times")
    parser.add_argument("--scenario", help="Optional mock transport scenario name to activate before connecting")
    parser.add_argument("--monitor", action="store_true", help="Run a passive monitoring loop instead of a one-shot probe")
    parser.add_argument("--listen-iterations", type=int, default=5, help="Number of receive polls")
    parser.add_argument("--listen-delay", type=float, default=0.05, help="Delay between receive polls in seconds")
    return parser


def build_probe_frames(adapter: ARMSmartHardwareAdapter, mode: str = "arm", ping: bool = True, servo_name_ids: list[int] | None = None) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    if ping:
        ping_frame = adapter.encode_ping_packet()
        frames.append({"kind": "ping", "hex": ping_frame.hex(), "bytes": ping_frame})
    if mode != "none":
        mode_frame = adapter.encode_mode_packet(mode)
        frames.append({"kind": f"set_mode_{mode}", "hex": mode_frame.hex(), "bytes": mode_frame})
    for servo_id in servo_name_ids or []:
        frame = adapter.encode_servo_name_get_packet(servo_id)
        frames.append({"kind": f"servo_name_get_{servo_id}", "hex": frame.hex(), "bytes": frame})
    return frames


def diagnose_link(profile_path: str | Path, mode: str = "arm", ping: bool = True, servo_name_ids: list[int] | None = None, scenario: str | None = None, listen_iterations: int = 5, listen_delay: float = 0.05) -> dict[str, Any]:
    profile = load_profile(profile_path)
    if scenario:
        profile.setdefault("transport", {})["active_scenario"] = scenario
    transport = transport_from_profile(profile)
    adapter = ARMSmartHardwareAdapter(profile)
    connected = transport.connect()
    sent_frames: list[dict[str, Any]] = []
    received_packets: list[dict[str, Any]] = []

    probe_frames = build_probe_frames(adapter, mode=mode, ping=ping, servo_name_ids=servo_name_ids)
    for frame in probe_frames:
        transport.send(frame["bytes"])
        sent_frames.append({"kind": frame["kind"], "hex": frame["hex"]})

    for _ in range(listen_iterations):
        packet = transport.receive()
        if packet:
            observation = adapter.decode_sensor_packet(packet)
            received_packets.append(
                {
                    "packet": {k: (v.hex() if isinstance(v, bytes) else v) for k, v in packet.items()},
                    "decoded_event": observation.metadata.get("decoded_event"),
                    "sensors": observation.sensors,
                    "metadata": observation.metadata,
                    "summary": adapter.summarize_observation(observation),
                }
            )
        time.sleep(listen_delay)

    return {
        "connected": connected,
        "transport_backend": getattr(transport, "name", "unknown"),
        "sent_frames": sent_frames,
        "received_packets": received_packets,
    }


def monitor_link(profile_path: str | Path, scenario: str | None = None, listen_iterations: int = 20, listen_delay: float = 0.1) -> dict[str, Any]:
    profile = load_profile(profile_path)
    if scenario:
        profile.setdefault("transport", {})["active_scenario"] = scenario
    transport = transport_from_profile(profile)
    adapter = ARMSmartHardwareAdapter(profile)
    connected = transport.connect()
    events: list[dict[str, Any]] = []
    for _ in range(listen_iterations):
        packet = transport.receive()
        if packet:
            observation = adapter.decode_sensor_packet(packet)
            events.append(adapter.summarize_observation(observation))
        time.sleep(listen_delay)
    return {
        "connected": connected,
        "transport_backend": getattr(transport, "name", "unknown"),
        "events": events,
    }


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = diagnose_link(
        profile_path=args.profile,
        mode=args.mode,
        ping=args.ping,
        servo_name_ids=args.servo_name_id,
        scenario=args.scenario,
        listen_iterations=args.listen_iterations,
        listen_delay=args.listen_delay,
    )
    if args.monitor:
        result = monitor_link(
            profile_path=args.profile,
            scenario=args.scenario,
            listen_iterations=args.listen_iterations,
            listen_delay=args.listen_delay,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()