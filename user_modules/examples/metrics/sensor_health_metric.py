from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ironengine_rl.interfaces import ActionCommand, StepResult


@dataclass(slots=True)
class SensorHealthMetric:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    name: str = "sensor_health"
    steps: int = 0
    front_range_alerts: int = 0
    air_quality_alerts: int = 0
    stop_gesture_events: int = 0
    average_battery_sum: float = 0.0

    def update(self, action: ActionCommand, step_result: StepResult) -> None:
        self.steps += 1
        sensors = step_result.observation.sensors
        cfg = self.config or {}
        front_range = float(sensors.get("front_range_m", 1.0))
        air_quality = float(sensors.get("air_quality_index", 0.0))
        stop_gesture = float(sensors.get("operator_stop_gesture", 0.0))
        battery_level = float(sensors.get("battery_level", 1.0))

        if front_range <= float(cfg.get("front_range_alert_threshold_m", 0.25)):
            self.front_range_alerts += 1
        if air_quality >= float(cfg.get("air_quality_alert_threshold", 150.0)):
            self.air_quality_alerts += 1
        if stop_gesture >= float(cfg.get("stop_gesture_threshold", 0.5)):
            self.stop_gesture_events += 1
        self.average_battery_sum += battery_level

    def summary(self, *, episodes: int, successes: int, reward_total: float) -> dict[str, Any]:
        average_battery = self.average_battery_sum / self.steps if self.steps else 0.0
        return {
            "front_range_alerts": self.front_range_alerts,
            "air_quality_alerts": self.air_quality_alerts,
            "stop_gesture_events": self.stop_gesture_events,
            "average_battery_level": average_battery,
            "steps": self.steps,
        }