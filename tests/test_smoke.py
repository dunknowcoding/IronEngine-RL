from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl.config import load_profile
from ironengine_rl.core import RuntimeOrchestrator
from ironengine_rl.core.safety import SafetyController
from ironengine_rl.diagnostics import build_probe_frames, diagnose_link, monitor_link
from ironengine_rl.hardware_adapters import ARMSmartHardwareAdapter, ProtocolParser, encode_frame
from ironengine_rl.hardware_adapters.transports import MockTransport, NullTransport, transport_from_profile
from ironengine_rl.interfaces import ActionCommand, InferenceResult, Observation
from ironengine_rl.simulation import DeterministicARMSmartEnv
from ironengine_rl.vision import camera_rig_from_profile, simulation_camera_rig_from_profile


class RuntimeSmokeTest(unittest.TestCase):
    def test_sim_profile_runs_and_writes_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "sim_minimal" / "profile.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["logs"]["run_dir"] = str(Path(temp_dir) / "logs")
            temp_profile = Path(temp_dir) / "profile.json"
            temp_profile.write_text(json.dumps(profile), encoding="utf-8")
            result = RuntimeOrchestrator(profile_path=str(temp_profile)).run(episodes=1, max_steps=12)
            summary_path = Path(result["summary_path"])
            self.assertTrue(summary_path.exists())
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("success_rate", payload)
            self.assertIn("task_metrics", payload)

    def test_sim_replay_profile_uses_replayed_camera_features(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "sim_replay" / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        rig = simulation_camera_rig_from_profile(profile)
        frames = rig.capture(0.0, {})
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].features["replay_available"], 1.0)
        self.assertEqual(frames[1].features["replay_available"], 1.0)

    def test_sim_replay_profile_runtime_writes_metrics(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "sim_replay" / "profile.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["logs"]["run_dir"] = str(Path(temp_dir) / "logs")
            temp_profile = Path(temp_dir) / "profile.json"
            temp_profile.write_text(json.dumps(profile), encoding="utf-8")
            result = RuntimeOrchestrator(profile_path=str(temp_profile)).run(episodes=1, max_steps=6)
            payload = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
            self.assertIn("task_metrics", payload)
            self.assertIn("average_visibility", payload["task_metrics"])
            self.assertGreater(payload["task_metrics"]["total_steps"], 0)

    def test_noisy_profile_exposes_fault_metadata(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "sim_noisy" / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        env = DeterministicARMSmartEnv(profile)
        env.reset()
        result = None
        for _ in range(12):
            result = env.step(ActionCommand())
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("anomalies", result.info)
        self.assertIn("fault_window_active", result.info["anomalies"])
        self.assertTrue(result.observation.metadata["fault_window_active"])

    def test_hardware_adapter_encodes_actions_and_shapes_packets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_hil" / "profile.json"
        profile = load_profile(profile_path)
        adapter = ARMSmartHardwareAdapter(profile)
        step_result = adapter.step(ActionCommand(chassis_forward=0.5, chassis_turn=-0.25, arm_lift=0.4, gripper_close=0.2))
        self.assertIn("encoded_command_hex", step_result.info)
        self.assertGreater(len(step_result.info["encoded_command_hex"]), 0)
        self.assertGreater(len(adapter.last_packets), 1)
        decoded = adapter.decode_sensor_packet(
            {
                "timestamp_s": 1.2,
                "protocol_command": 18,
                "payload_bytes": bytes([1]),
                "connection_alive": 1.0,
                "battery_level": 0.8,
                "dash_visibility": 0.7,
                "claw_visibility": 0.6,
                "imu_roll_deg": 5.0,
            }
        )
        self.assertEqual(decoded.metadata["source"], "hardware_packet")
        self.assertEqual(len(decoded.cameras), 2)
        self.assertEqual(decoded.metadata["decoded_event"], "mode_ack")
        self.assertEqual(decoded.metadata["pc_mode_name"], "arm")

    def test_transport_and_camera_fallbacks_are_profile_driven(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_hil" / "profile.json"
        profile = load_profile(profile_path)
        transport = transport_from_profile(profile)
        self.assertIsInstance(transport, NullTransport)
        camera_rig = camera_rig_from_profile(profile)
        frames = camera_rig.capture(0.5)
        self.assertEqual(len(frames), 2)
        self.assertEqual({frame.role for frame in frames}, {"dash", "claw"})

    def test_mock_transport_injects_known_replies(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        profile = load_profile(profile_path)
        transport = transport_from_profile(profile)
        self.assertIsInstance(transport, MockTransport)
        adapter = ARMSmartHardwareAdapter(profile)
        transport.connect()
        for frame in build_probe_frames(adapter, mode="arm", ping=True, servo_name_ids=[2]):
            transport.send(frame["bytes"])
        events = []
        while True:
            packet = transport.receive()
            if not packet:
                break
            observation = adapter.decode_sensor_packet(packet)
            events.append(observation.metadata["decoded_event"])
        self.assertEqual(events, ["pong", "mode_ack", "servo_name_reply", "telemetry_snapshot", "telemetry_snapshot"])

    def test_protocol_codec_round_trips_mode_ack(self) -> None:
        parser = ProtocolParser()
        frames = parser.feed(encode_frame(0x12, bytes([0x02])))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].command, 0x12)
        self.assertEqual(frames[0].payload, bytes([0x02]))

    def test_diagnostic_cli_logic_reports_sent_probe_frames(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        result = diagnose_link(profile_path=profile_path, mode="arm", ping=True, servo_name_ids=[2], scenario="nominal", listen_iterations=1, listen_delay=0.0)
        self.assertEqual(result["transport_backend"], "mock")
        self.assertEqual(len(result["sent_frames"]), 3)
        self.assertEqual(result["received_packets"][0]["decoded_event"], "pong")
        self.assertIn("battery_level", result["received_packets"][0]["summary"])

    def test_probe_builder_and_monitor_helpers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        profile = load_profile(profile_path)
        adapter = ARMSmartHardwareAdapter(profile)
        frames = build_probe_frames(adapter, mode="car", ping=True, servo_name_ids=[1, 3])
        self.assertEqual([frame["kind"] for frame in frames], ["ping", "set_mode_car", "servo_name_get_1", "servo_name_get_3"])
        monitor_result = monitor_link(profile_path=profile_path, scenario="nominal", listen_iterations=1, listen_delay=0.0)
        self.assertEqual(monitor_result["transport_backend"], "mock")
        self.assertEqual(monitor_result["events"][0]["decoded_event"], "telemetry_snapshot")
        self.assertAlmostEqual(monitor_result["events"][0]["battery_level"], 0.92)

    def test_mock_scenarios_switch_monitor_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        collision_result = monitor_link(profile_path=profile_path, scenario="collision_spike", listen_iterations=2, listen_delay=0.0)
        self.assertGreaterEqual(collision_result["events"][1]["battery_level"], 0.82)
        low_battery_result = monitor_link(profile_path=profile_path, scenario="low_battery", listen_iterations=2, listen_delay=0.0)
        self.assertAlmostEqual(low_battery_result["events"][1]["battery_level"], 0.18)
        grasp_result = monitor_link(profile_path=profile_path, scenario="grasp_success", listen_iterations=2, listen_delay=0.0)
        self.assertEqual(grasp_result["events"][1]["decoded_event"], "telemetry_snapshot")

    def test_reactive_mock_scenario_responds_to_actions(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        profile = load_profile(profile_path)
        profile["transport"]["active_scenario"] = "reactive_grasp"
        transport = transport_from_profile(profile)
        adapter = ARMSmartHardwareAdapter(profile)
        self.assertTrue(transport.connect())
        for frame in build_probe_frames(adapter, mode="arm", ping=True, servo_name_ids=[]):
            transport.send(frame["bytes"])
        action = ActionCommand(chassis_forward=0.8, arm_extend=1.0, gripper_close=1.0)
        for packet in adapter.encode_action_packets(action):
            transport.send(packet)
        observed_events = []
        object_grasped_values = []
        while True:
            packet = transport.receive()
            if not packet:
                break
            observation = adapter.decode_sensor_packet(packet)
            observed_events.append(observation.metadata["decoded_event"])
            object_grasped_values.append(observation.sensors.get("object_grasped", 0.0))
        self.assertIn("telemetry_snapshot", observed_events)
        self.assertGreaterEqual(max(object_grasped_values), 1.0)

    def test_runtime_can_step_through_reactive_mock_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "armsmart_mock" / "profile.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = load_profile(profile_path)
            profile["transport"]["active_scenario"] = "reactive_grasp"
            profile["logs"]["run_dir"] = str(Path(temp_dir) / "logs")
            temp_profile = Path(temp_dir) / "profile.json"
            temp_profile.write_text(json.dumps(profile), encoding="utf-8")
            result = RuntimeOrchestrator(profile_path=str(temp_profile)).run(episodes=1, max_steps=8)
            payload = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
            self.assertIn("success_rate", payload)
            self.assertGreaterEqual(payload["reward_total"], 0.0)
            self.assertIn("task_metrics", payload)

    def test_safety_stops_on_stale_observation(self) -> None:
        profile = {
            "safety": {
                "stale_observation_stop_steps": 2,
                "connection_required": False,
            }
        }
        controller = SafetyController(profile=profile)
        inference = InferenceResult(task_phase="approach", state_estimate={}, reward_hints={})
        observation = Observation(timestamp_s=1.0, sensors={"collision_risk": 0.0, "battery_level": 1.0}, cameras=[])
        action = ActionCommand(chassis_forward=0.4)
        first = controller.apply(action, observation, inference)
        second = controller.apply(action, observation, inference)
        third = controller.apply(action, observation, inference)
        self.assertEqual(first.auxiliary.get("safety_stop"), None)
        self.assertEqual(second.auxiliary.get("safety_stop"), None)
        self.assertEqual(third.auxiliary.get("safety_stop"), 1.0)


if __name__ == "__main__":
    unittest.main()
