
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.contracts import PlatformManifest
from ironengine_rl.hardware_adapters import ARMSmartHardwareAdapter
from ironengine_rl.interfaces import EnvironmentPort
from ironengine_rl.platforms.base import PlatformAdapter
from ironengine_rl.simulation import DeterministicARMSmartEnv


@dataclass(slots=True)
class SimulationPlatformAdapter(PlatformAdapter):
    def build_environment(self, profile: dict[str, Any]) -> EnvironmentPort:
        return DeterministicARMSmartEnv(profile)

    def build_manifest(self, profile: dict[str, Any]) -> PlatformManifest:
        simulator_cfg = profile.get('simulator', {})
        vision_cfg = profile.get('vision', {})
        return PlatformManifest(
            name=profile.get('platform', {}).get('name', 'simulation_generic'),
            platform_type='simulation',
            description='Normalized simulation platform contract for deterministic or noisy environments.',
            transport_backends=['in_process'],
            observation_fields=[
                'object_dx', 'object_dy', 'object_distance', 'heading_error_deg', 'arm_height',
                'arm_extension', 'wrist_yaw_deg', 'gripper_close', 'claw_distance', 'claw_alignment',
                'vertical_error', 'pregrasp_ready', 'target_reachable', 'collision_risk',
                'battery_level', 'object_grasped', 'scene_object_count', 'distractor_count', 'target_object_visible',
            ],
            camera_roles=[vision_cfg.get('dash_role', 'dash'), vision_cfg.get('claw_role', 'claw')],
            action_channels=[
                'chassis_forward', 'chassis_strafe', 'chassis_turn', 'arm_lift',
                'arm_extend', 'wrist_yaw', 'gripper_close',
            ],
            safety_features=['collision_threshold', 'battery_threshold', 'stale_observation_check'],
            timing={'dt_s': float(simulator_cfg.get('dt_s', 0.1)), 'max_steps': int(simulator_cfg.get('max_steps', 50))},
            capabilities={'noise_enabled': bool(simulator_cfg.get('enable_noise', False))},
        )


@dataclass(slots=True)
class ARMSmartPlatformAdapter(PlatformAdapter):
    def build_environment(self, profile: dict[str, Any]) -> EnvironmentPort:
        return ARMSmartHardwareAdapter(profile)

    def build_manifest(self, profile: dict[str, Any]) -> PlatformManifest:
        transport_cfg = profile.get('transport', {})
        vision_cfg = profile.get('vision', {})
        return PlatformManifest(
            name=profile.get('platform', {}).get('name', 'armsmart_reference'),
            platform_type='hardware',
            description='ARMSmart-compatible reference hardware platform with transport and camera abstractions.',
            transport_backends=[transport_cfg.get('backend', 'null'), 'serial', 'udp', 'mock'],
            observation_fields=[
                'connection_alive', 'battery_level', 'collision_risk', 'object_grasped',
                'object_dx', 'object_dy', 'imu_roll_deg', 'imu_pitch_deg', 'imu_yaw_deg',
                'arm_height', 'arm_extension', 'claw_alignment', 'gripper_close', 'heartbeat_ok',
            ],
            camera_roles=[vision_cfg.get('dash_role', 'dash'), vision_cfg.get('claw_role', 'claw')],
            action_channels=[
                'chassis_forward', 'chassis_strafe', 'chassis_turn', 'arm_lift',
                'arm_extend', 'wrist_yaw', 'gripper_close',
            ],
            safety_features=['collision_threshold', 'battery_threshold', 'connection_required', 'stale_observation_check'],
            timing={
                'transport_timeout_s': float(transport_cfg.get('timeout_s', 0.05)),
                'read_chunk_size': int(transport_cfg.get('read_chunk_size', 256)),
            },
            capabilities={
                'default_mode': transport_cfg.get('default_mode', 'arm'),
                'protocol_commands': sorted(transport_cfg.get('protocol_commands', {}).keys()),
                'camera_backend': vision_cfg.get('backend', 'placeholder'),
            },
        )


@dataclass(slots=True)
class GenericHardwarePlatformAdapter(PlatformAdapter):
    def build_environment(self, profile: dict[str, Any]) -> EnvironmentPort:
        return ARMSmartHardwareAdapter(profile)

    def build_manifest(self, profile: dict[str, Any]) -> PlatformManifest:
        platform_cfg = profile.get('platform', {})
        capabilities = platform_cfg.get('capabilities', {})
        return PlatformManifest(
            name=platform_cfg.get('name', 'custom_hardware'),
            platform_type=platform_cfg.get('type', 'custom_hardware'),
            description=platform_cfg.get('description', 'User-defined hardware platform manifest.'),
            transport_backends=list(capabilities.get('transport_backends', [profile.get('transport', {}).get('backend', 'serial')])),
            observation_fields=list(capabilities.get('observation_fields', [])),
            camera_roles=list(capabilities.get('camera_roles', [])),
            action_channels=list(capabilities.get('action_channels', [])),
            safety_features=list(capabilities.get('safety_features', [])),
            timing=dict(capabilities.get('timing', {})),
            capabilities=dict(capabilities),
        )


def platform_adapter_from_profile(profile: dict[str, Any]) -> PlatformAdapter:
    runtime_mode = profile.get('runtime', {}).get('mode', 'simulation')
    platform_cfg = profile.get('platform', {})
    platform_type = platform_cfg.get('type')
    if platform_cfg.get('capabilities'):
        return GenericHardwarePlatformAdapter()
    if platform_type == 'armsmart_reference' or runtime_mode == 'hardware':
        return ARMSmartPlatformAdapter()
    return SimulationPlatformAdapter()


def build_platform_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    return platform_adapter_from_profile(profile).build_manifest(profile).to_dict()
