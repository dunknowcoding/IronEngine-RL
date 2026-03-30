
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def load_profile(profile_path: str | Path) -> dict[str, Any]:
    path = Path(profile_path)
    with path.open('r', encoding='utf-8') as handle:
        return normalize_profile(json.load(handle))


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(profile)
    _normalize_grouped_hardware_config(normalized)
    framework_modules = normalized.get('framework', {}).get('modules', {})
    if framework_modules:
        if 'model_provider' not in normalized and 'inference_engine' in framework_modules:
            normalized['model_provider'] = deepcopy(framework_modules['inference_engine'])
        if 'evaluation' not in normalized and 'evaluation' in framework_modules:
            normalized['evaluation'] = deepcopy(framework_modules['evaluation'])
        if 'agent' not in normalized and 'agent' in framework_modules:
            normalized['agent'] = deepcopy(framework_modules['agent'])
        if 'repository' not in normalized and 'repository' in framework_modules:
            normalized['repository'] = deepcopy(framework_modules['repository'])
        if 'boundary_conditions' not in normalized and 'boundary_conditions' in framework_modules:
            normalized['boundary_conditions'] = deepcopy(framework_modules['boundary_conditions'])
        if 'model_provider' in normalized and 'update_strategy' in framework_modules:
            normalized['model_provider'].setdefault('update_strategy', deepcopy(framework_modules['update_strategy']))
    normalized.setdefault('evaluation', {'task': 'tabletop_grasp', 'metrics': ['task_performance', 'boundary_violations']})
    normalized.setdefault('agent', {'type': 'heuristic'})
    normalized.setdefault('boundary_conditions', deepcopy(normalized.get('safety', {'type': 'safety_controller'})))
    normalized['boundary_conditions'].setdefault('type', normalized.get('boundary_conditions', {}).get('type', 'safety_controller'))
    normalized.setdefault('repository', {'type': 'knowledge_repository'})
    normalized.setdefault(
        'platform',
        {
            'name': normalized.get('runtime', {}).get('mode', 'simulation_generic'),
            'type': normalized.get('runtime', {}).get('mode', 'simulation'),
        },
    )
    normalized.setdefault('validation', {'strict': False, 'require_compatibility': True})
    return normalized


def _normalize_grouped_hardware_config(profile: dict[str, Any]) -> None:
    hardware_cfg = profile.get('hardware')
    if not isinstance(hardware_cfg, dict):
        return

    platform_cfg = hardware_cfg.get('platform', {}) if isinstance(hardware_cfg.get('platform'), dict) else {}
    connection_cfg = hardware_cfg.get('connection', {}) if isinstance(hardware_cfg.get('connection'), dict) else {}
    protocol_cfg = hardware_cfg.get('protocol', {}) if isinstance(hardware_cfg.get('protocol'), dict) else {}
    cameras_cfg = hardware_cfg.get('cameras', {}) if isinstance(hardware_cfg.get('cameras'), dict) else {}
    safety_cfg = hardware_cfg.get('safety', {}) if isinstance(hardware_cfg.get('safety'), dict) else {}
    mock_cfg = hardware_cfg.get('mock', {}) if isinstance(hardware_cfg.get('mock'), dict) else {}

    profile.setdefault('runtime', {})
    profile['runtime'].setdefault('mode', 'hardware')
    profile['runtime'].setdefault('stage', 'C')

    if platform_cfg:
        platform = profile.setdefault('platform', {})
        platform.setdefault('name', platform_cfg.get('name', 'custom_hardware'))
        platform.setdefault('type', platform_cfg.get('type', 'custom_hardware'))
        if 'description' in platform_cfg:
            platform.setdefault('description', platform_cfg['description'])
        if 'capabilities' in platform_cfg and isinstance(platform_cfg['capabilities'], dict):
            platform.setdefault('capabilities', deepcopy(platform_cfg['capabilities']))

    transport = profile.setdefault('transport', {})
    transport.setdefault('backend', connection_cfg.get('backend', transport.get('backend', 'null')))
    transport.setdefault('timeout_s', float(connection_cfg.get('timeout_s', transport.get('timeout_s', 0.05))))
    transport.setdefault('read_chunk_size', int(connection_cfg.get('read_chunk_size', transport.get('read_chunk_size', 256))))
    transport.setdefault('default_mode', connection_cfg.get('default_mode', transport.get('default_mode', 'arm')))
    transport.setdefault('ble_enabled', bool(connection_cfg.get('ble_enabled', transport.get('ble_enabled', True))))

    serial_cfg = connection_cfg.get('serial', {}) if isinstance(connection_cfg.get('serial'), dict) else {}
    if serial_cfg:
        transport.setdefault('serial_port', serial_cfg.get('port', transport.get('serial_port', 'COM5')))
        transport.setdefault('baud_rate', int(serial_cfg.get('baud_rate', transport.get('baud_rate', 115200))))

    udp_cfg = connection_cfg.get('udp', {}) if isinstance(connection_cfg.get('udp'), dict) else {}
    if udp_cfg:
        merged_udp = dict(transport.get('udp', {})) if isinstance(transport.get('udp'), dict) else {}
        if 'host' in udp_cfg:
            merged_udp.setdefault('host', udp_cfg['host'])
        if 'port' in udp_cfg:
            merged_udp.setdefault('port', udp_cfg['port'])
        merged_udp.setdefault('timeout_s', float(udp_cfg.get('timeout_s', transport.get('timeout_s', 0.05))))
        transport['udp'] = merged_udp

    if 'active_scenario' in mock_cfg:
        transport.setdefault('active_scenario', mock_cfg['active_scenario'])
    if 'packets' in mock_cfg and isinstance(mock_cfg['packets'], list):
        transport.setdefault('mock_packets', deepcopy(mock_cfg['packets']))
    if 'scenarios' in mock_cfg and isinstance(mock_cfg['scenarios'], dict):
        transport.setdefault('mock_scenarios', deepcopy(mock_cfg['scenarios']))

    commands = protocol_cfg.get('commands') if isinstance(protocol_cfg.get('commands'), dict) else None
    if commands:
        transport.setdefault('protocol_commands', deepcopy(commands))

    vision = profile.setdefault('vision', {})
    vision.setdefault('backend', cameras_cfg.get('backend', vision.get('backend', 'placeholder')))
    dash_cfg = cameras_cfg.get('dash', {}) if isinstance(cameras_cfg.get('dash'), dict) else {}
    claw_cfg = cameras_cfg.get('claw', {}) if isinstance(cameras_cfg.get('claw'), dict) else {}
    if dash_cfg:
        vision.setdefault('dash_camera_id', dash_cfg.get('camera_id', vision.get('dash_camera_id', 'dash_cam_hw')))
        if 'device_index' in dash_cfg:
            vision.setdefault('dash_device_index', int(dash_cfg['device_index']))
    if claw_cfg:
        vision.setdefault('claw_camera_id', claw_cfg.get('camera_id', vision.get('claw_camera_id', 'claw_cam_hw')))
        if 'device_index' in claw_cfg:
            vision.setdefault('claw_device_index', int(claw_cfg['device_index']))
    if dash_cfg.get('role'):
        vision.setdefault('dash_role', dash_cfg['role'])
    if claw_cfg.get('role'):
        vision.setdefault('claw_role', claw_cfg['role'])

    safety = profile.setdefault('safety', {})
    for key, value in safety_cfg.items():
        safety.setdefault(key, value)
