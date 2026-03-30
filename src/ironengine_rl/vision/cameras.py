from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ironengine_rl.interfaces import CameraFrame


@dataclass(slots=True)
class SyntheticCameraRig:
    dash_camera_id: str
    claw_camera_id: str

    def capture(self, timestamp_s: float, world_state: dict[str, float]) -> list[CameraFrame]:
        object_distance = world_state["object_distance"]
        heading_error = abs(world_state["heading_error_deg"])
        claw_distance = world_state["claw_distance"]
        claw_alignment = world_state["claw_alignment"]
        dash_visibility = max(0.0, 1.0 - object_distance / 3.5)
        claw_visibility = max(0.0, 1.0 - claw_distance / 1.5) * claw_alignment
        scene_detections = list(world_state.get("scene_detections", []))
        target_label = str(world_state.get("target_object_label", "target_object"))
        distractor_visibility = max(
            [float(item.get("confidence", 0.0)) for item in scene_detections if not item.get("is_target")],
            default=0.0,
        )
        return [
            CameraFrame(
                camera_id=self.dash_camera_id,
                role="dash",
                timestamp_s=timestamp_s,
                features={
                    "target_visibility": dash_visibility,
                    "heading_alignment": max(0.0, 1.0 - heading_error / 90.0),
                    "scene_object_count": float(len(scene_detections)),
                    "distractor_visibility": distractor_visibility,
                },
                detections=scene_detections or [{"label": target_label, "confidence": dash_visibility, "is_target": True}],
            ),
            CameraFrame(
                camera_id=self.claw_camera_id,
                role="claw",
                timestamp_s=timestamp_s,
                features={
                    "target_visibility": claw_visibility,
                    "target_centered": claw_alignment,
                },
                detections=[{"label": target_label, "confidence": claw_visibility, "is_target": True}],
            ),
        ]


@dataclass(slots=True)
class NullCameraProvider:
    camera_id: str
    role: str

    def capture(self, timestamp_s: float) -> CameraFrame:
        return CameraFrame(
            camera_id=self.camera_id,
            role=self.role,
            timestamp_s=timestamp_s,
            features={"target_visibility": 0.0},
            detections=[],
        )


@dataclass(slots=True)
class ReplayCameraProvider:
    camera_id: str
    role: str
    frames: list[dict[str, Any]]
    loop: bool = True
    index: int = 0

    def capture(self, timestamp_s: float) -> CameraFrame:
        if not self.frames:
            return CameraFrame(
                camera_id=self.camera_id,
                role=self.role,
                timestamp_s=timestamp_s,
                features={"target_visibility": 0.0, "replay_available": 0.0},
                detections=[],
            )
        frame = self.frames[self.index]
        if self.loop:
            self.index = (self.index + 1) % len(self.frames)
        elif self.index < len(self.frames) - 1:
            self.index += 1
        return CameraFrame(
            camera_id=self.camera_id,
            role=self.role,
            timestamp_s=float(frame.get("timestamp_s", timestamp_s)),
            features={key: float(value) for key, value in frame.get("features", {}).items()},
            detections=list(frame.get("detections", [])),
        )


@dataclass(slots=True)
class ReplayCameraRig:
    dash_provider: ReplayCameraProvider
    claw_provider: ReplayCameraProvider

    def capture(self, timestamp_s: float, world_state: dict[str, float] | None = None) -> list[CameraFrame]:
        return [self.dash_provider.capture(timestamp_s), self.claw_provider.capture(timestamp_s)]


@dataclass(slots=True)
class OpenCVCameraProvider:
    camera_id: str
    role: str
    device_index: int
    capture_handle: Any = None

    def capture(self, timestamp_s: float) -> CameraFrame:
        try:
            import cv2  # type: ignore
        except Exception:
            return CameraFrame(
                camera_id=self.camera_id,
                role=self.role,
                timestamp_s=timestamp_s,
                features={"target_visibility": 0.0, "backend_available": 0.0},
                detections=[],
            )
        if self.capture_handle is None:
            self.capture_handle = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        ok, frame = self.capture_handle.read()
        if not ok or frame is None:
            return CameraFrame(
                camera_id=self.camera_id,
                role=self.role,
                timestamp_s=timestamp_s,
                features={"target_visibility": 0.0, "backend_available": 1.0},
                detections=[],
            )
        height, width = frame.shape[:2]
        brightness = float(frame.mean()) / 255.0
        return CameraFrame(
            camera_id=self.camera_id,
            role=self.role,
            timestamp_s=timestamp_s,
            features={
                "target_visibility": brightness,
                "frame_width": float(width),
                "frame_height": float(height),
                "backend_available": 1.0,
            },
            detections=[],
        )


@dataclass(slots=True)
class HardwareCameraRig:
    dash_camera_id: str
    claw_camera_id: str
    providers: dict[str, Any]

    def capture(self, timestamp_s: float, packet: dict[str, Any] | None = None) -> list[CameraFrame]:
        packet = packet or {}
        frames: list[CameraFrame] = []
        for role, provider in self.providers.items():
            visibility_key = f"{role}_visibility"
            if visibility_key in packet:
                frames.append(
                    CameraFrame(
                        camera_id=provider.camera_id,
                        role=role,
                        timestamp_s=timestamp_s,
                        features={"target_visibility": float(packet.get(visibility_key, 0.0))},
                        detections=[],
                    )
                )
            else:
                frames.append(provider.capture(timestamp_s))
        return frames


def simulation_camera_rig_from_profile(profile: dict[str, Any]) -> Any:
    vision_cfg = profile.get("vision", {})
    backend = vision_cfg.get("backend", "synthetic")
    if backend == "replay":
        providers = _build_replay_providers(vision_cfg)
        return ReplayCameraRig(dash_provider=providers["dash"], claw_provider=providers["claw"])
    return SyntheticCameraRig(
        dash_camera_id=vision_cfg.get("dash_camera_id", "dash_cam"),
        claw_camera_id=vision_cfg.get("claw_camera_id", "claw_cam"),
    )


def camera_rig_from_profile(profile: dict[str, Any]) -> HardwareCameraRig:
    vision_cfg = profile.get("vision", {})
    dash_camera_id = vision_cfg.get("dash_camera_id", "dash_cam_hw")
    claw_camera_id = vision_cfg.get("claw_camera_id", "claw_cam_hw")
    backend = vision_cfg.get("backend", "placeholder")
    if backend == "opencv":
        providers = {
            "dash": OpenCVCameraProvider(camera_id=dash_camera_id, role="dash", device_index=int(vision_cfg.get("dash_device_index", 0))),
            "claw": OpenCVCameraProvider(camera_id=claw_camera_id, role="claw", device_index=int(vision_cfg.get("claw_device_index", 1))),
        }
    elif backend == "replay":
        providers = _build_replay_providers(vision_cfg)
    else:
        providers = {
            "dash": NullCameraProvider(camera_id=dash_camera_id, role="dash"),
            "claw": NullCameraProvider(camera_id=claw_camera_id, role="claw"),
        }
    return HardwareCameraRig(
        dash_camera_id=dash_camera_id,
        claw_camera_id=claw_camera_id,
        providers=providers,
    )


def _build_replay_providers(vision_cfg: dict[str, Any]) -> dict[str, ReplayCameraProvider]:
    dash_camera_id = vision_cfg.get("dash_camera_id", "dash_cam")
    claw_camera_id = vision_cfg.get("claw_camera_id", "claw_cam")
    loop = bool(vision_cfg.get("replay_loop", True))
    if replay_file := vision_cfg.get("replay_file"):
        payload = json.loads(Path(replay_file).read_text(encoding="utf-8"))
        dash_frames = list(payload.get("dash", []))
        claw_frames = list(payload.get("claw", []))
    else:
        dash_frames = list(json.loads(Path(vision_cfg.get("dash_replay_file", "")).read_text(encoding="utf-8"))) if vision_cfg.get("dash_replay_file") else []
        claw_frames = list(json.loads(Path(vision_cfg.get("claw_replay_file", "")).read_text(encoding="utf-8"))) if vision_cfg.get("claw_replay_file") else []
    return {
        "dash": ReplayCameraProvider(camera_id=dash_camera_id, role="dash", frames=dash_frames, loop=loop),
        "claw": ReplayCameraProvider(camera_id=claw_camera_id, role="claw", frames=claw_frames, loop=loop),
    }
