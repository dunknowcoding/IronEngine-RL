from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

from ironengine_rl.config import load_profile
from ironengine_rl.framework import build_validation_report
from ironengine_rl.hardware_adapters.protocol_codec import encode_frame
from ironengine_rl.hardware_adapters.transports import SerialTransport
from ironengine_rl.vision.cameras import OpenCVCameraProvider
from ironengine_rl.inference import provider_from_profile
from ironengine_rl.interfaces import CameraFrame, Observation


class _FakeSerialHandle:
    def __init__(self, *args, **kwargs) -> None:
        self.writes: list[bytes] = []
        self._read_payload = encode_frame(0x12, bytes([0x01]))

    def write(self, payload: bytes) -> int:
        self.writes.append(payload)
        return len(payload)

    def read(self, size: int) -> bytes:
        data = self._read_payload[:size]
        self._read_payload = b""
        return data


class IntegrationBehaviorTest(unittest.TestCase):
    def test_serial_transport_uses_mocked_serial_backend(self) -> None:
        fake_serial_module = types.SimpleNamespace(Serial=_FakeSerialHandle)
        profile = {
            "transport": {
                "backend": "serial",
                "serial_port": "COM9",
                "baud_rate": 57600,
                "timeout_s": 0.1,
                "read_chunk_size": 256,
            }
        }
        transport = SerialTransport(profile)
        with mock.patch.dict(sys.modules, {"serial": fake_serial_module}):
            self.assertTrue(transport.connect())
            self.assertTrue(transport.send(b"abc"))
            packet = transport.receive()
        self.assertIsNotNone(packet)
        assert packet is not None
        self.assertEqual(packet["protocol_command"], 0x12)
        self.assertEqual(transport.serial_handle.writes, [b"abc"])

    def test_opencv_camera_provider_uses_mocked_backend(self) -> None:
        class _FakeCapture:
            def __init__(self, device_index: int, backend: int) -> None:
                self.device_index = device_index
                self.backend = backend

            def read(self):
                frame = [[ [255, 255, 255] for _ in range(4)] for _ in range(3)]
                class _Frame:
                    shape = (3, 4, 3)
                    def mean(self):
                        return 255.0
                return True, _Frame()

        fake_cv2 = types.SimpleNamespace(VideoCapture=_FakeCapture, CAP_DSHOW=700)
        provider = OpenCVCameraProvider(camera_id="dash_cam", role="dash", device_index=0)
        with mock.patch.dict(sys.modules, {"cv2": fake_cv2}):
            frame = provider.capture(0.2)
        self.assertEqual(frame.camera_id, "dash_cam")
        self.assertEqual(frame.features["backend_available"], 1.0)
        self.assertEqual(frame.features["frame_width"], 4.0)
        self.assertEqual(frame.features["frame_height"], 3.0)

    def test_anomaly_customization_example_validates_and_emits_notes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "examples" / "plugins" / "anomaly_customization" / "profile.json"
        profile = load_profile(profile_path)
        report = build_validation_report(profile)
        self.assertTrue(report["schema"]["valid"])
        self.assertTrue(report["compatibility"]["compatible"])
        provider = provider_from_profile(profile)
        observation = Observation(
            timestamp_s=0.5,
            sensors={
                "object_dx": 0.6,
                "object_dy": 0.0,
                "claw_alignment": 0.3,
                "arm_extension": 0.2,
                "arm_height": 0.2,
                "battery_level": 0.18,
                "collision_risk": 0.72,
            },
            cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.5, features={"target_visibility": 0.2})],
            metadata={"fault_window_active": True},
        )
        result = provider.infer(observation, {"repository_notes": []})
        self.assertIn("Anomaly-aware inference provider active.", result.notes)
        self.assertIn("camera_dropout", result.anomalies)
        self.assertIn("visibility_below_threshold", result.anomalies)
        self.assertIn("battery_margin_low", result.anomalies)
        self.assertIn("fault_window_active", result.anomalies)


class PackagingMetadataTest(unittest.TestCase):
    def test_pyproject_declares_expected_optional_dependency_groups(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        payload = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
        optional = payload["project"]["optional-dependencies"]
        self.assertIn("llm", optional)
        self.assertIn("hardware", optional)
        self.assertIn("torch", optional)
        self.assertIn("examples", optional)
        self.assertIn("all", optional)
        self.assertTrue(any(item.startswith("requests") for item in optional["llm"]))
        self.assertTrue(any(item.startswith("pyserial") for item in optional["hardware"]))
        self.assertTrue(any(item.startswith("torch") for item in optional["torch"]))


if __name__ == "__main__":
    unittest.main()
