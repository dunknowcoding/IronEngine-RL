
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ironengine_rl.contracts import PlatformManifest
from ironengine_rl.interfaces import EnvironmentPort


class PlatformAdapter(ABC):
    @abstractmethod
    def build_environment(self, profile: dict[str, Any]) -> EnvironmentPort:
        raise NotImplementedError

    @abstractmethod
    def build_manifest(self, profile: dict[str, Any]) -> PlatformManifest:
        raise NotImplementedError
