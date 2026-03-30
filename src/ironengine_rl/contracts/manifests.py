
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class InterfaceContract:
    observation_fields: list[str] = field(default_factory=list)
    camera_roles: list[str] = field(default_factory=list)
    action_channels: list[str] = field(default_factory=list)
    repository_context_keys: list[str] = field(default_factory=list)
    optional_dependencies: list[str] = field(default_factory=list)
    runtime_modes: list[str] = field(default_factory=lambda: ['simulation', 'hardware'])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModuleManifest:
    name: str
    module_type: str
    api_version: str = '1.0'
    description: str = ''
    implementation_path: str = ''
    style: str = ''
    contract: InterfaceContract = field(default_factory=InterfaceContract)
    config_schema: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['contract'] = self.contract.to_dict()
        return payload


@dataclass(slots=True)
class PlatformManifest:
    name: str
    platform_type: str
    api_version: str = '1.0'
    description: str = ''
    transport_backends: list[str] = field(default_factory=list)
    observation_fields: list[str] = field(default_factory=list)
    camera_roles: list[str] = field(default_factory=list)
    action_channels: list[str] = field(default_factory=list)
    safety_features: list[str] = field(default_factory=list)
    timing: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityIssue:
    severity: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityReport:
    compatible: bool
    issues: list[CompatibilityIssue] = field(default_factory=list)
    checked_components: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'compatible': self.compatible,
            'issues': [issue.to_dict() for issue in self.issues],
            'checked_components': dict(self.checked_components),
        }
