from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ironengine_rl.inference.llm_context import build_role_and_task_preamble
from ironengine_rl.inference.ollama_client import apply_ollama_decision, request_ollama_decision
from ironengine_rl.interfaces import InferenceResult, Observation
from ironengine_rl.model_providers.rule_based import RuleBasedModelProvider


@dataclass(slots=True)
class ARMSmartLocalLLMProvider:
    profile: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    fallback: RuleBasedModelProvider = field(default_factory=RuleBasedModelProvider)
    _cached_signature: str | None = field(default=None, init=False)
    _cached_decision: Any = field(default=None, init=False)
    _cached_uses_remaining: int = field(default=0, init=False)

    def infer(self, observation: Observation, repository_context: dict[str, Any]) -> InferenceResult:
        fallback = self.fallback.infer(observation, repository_context)
        fallback = self._enrich_fallback(fallback, observation)
        prompt, metadata = self._build_prompt(observation, repository_context)
        live_prompt = self._build_live_prompt(observation, repository_context, metadata, fallback)
        decision = self._resolve_live_decision(live_prompt, observation, fallback)
        resolved = apply_ollama_decision(fallback, decision)
        notes = list(resolved.notes)
        notes.extend(
            [
                "Local LLM ARMSmart provider active.",
                f"Configured model: {(self.config or {}).get('model', 'unspecified')}",
                f"Role contract: {metadata.get('role_contract_file', 'SOUL.md')}",
                f"Resolved task: {metadata.get('task_name', 'framework_task')}",
                f"Task goal: {metadata.get('task_goal', 'unspecified')}",
                f"Action scheme: {repository_context.get('action_scheme', {}).get('name', 'direct_channel_control')}",
                f"Prompt preview length: {len(live_prompt) if self._live_mode_enabled() else len(prompt)} characters",
            ]
        )
        return InferenceResult(
            task_phase=resolved.task_phase,
            state_estimate={**resolved.state_estimate, "llm_prompt_chars": float(len(live_prompt) if self._live_mode_enabled() else len(prompt))},
            reward_hints=dict(resolved.reward_hints),
            anomalies=list(resolved.anomalies),
            visual_summary=dict(resolved.visual_summary),
            notes=notes,
        )

    def _build_prompt(self, observation: Observation, repository_context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        cfg = self.config or {}
        role_and_task, metadata = build_role_and_task_preamble(self.profile or {}, cfg, repository_context)
        return (
            f"{role_and_task}\n"
            f"System prompt override: {cfg.get('system_prompt', 'You are the local ARMSmart planner.')}\n"
            f"Action scheme: {repository_context.get('action_scheme', {})}\n"
            f"Knowledge repository: {repository_context.get('knowledge_repository', {})}\n"
            f"Database mode: {repository_context.get('database', {})}\n"
            f"Recent rewards: {repository_context.get('recent_reward_summary', {})}\n"
            f"State summary: {repository_context.get('state_summary', {})}\n"
            f"Sensors: {observation.sensors}\n"
            f"Vision features: {[camera.features for camera in observation.cameras]}\n"
            f"Vision detections: {[camera.detections for camera in observation.cameras]}\n"
            f"Observation metadata: {observation.metadata}"
        ), metadata

    def _enrich_fallback(self, fallback: InferenceResult, observation: Observation) -> InferenceResult:
        visibility = 0.0
        if observation.cameras:
            visibility = sum(camera.features.get("target_visibility", 0.0) for camera in observation.cameras) / len(observation.cameras)
        distance = float(fallback.state_estimate.get("object_distance", observation.sensors.get("object_distance", 1.0)))
        alignment = float(observation.sensors.get("claw_alignment", 0.0))
        pregrasp_ready = float(observation.sensors.get("pregrasp_ready", 0.0))
        heuristic_confidence = max(0.0, min(1.0, 0.42 * alignment + 0.28 * visibility + 0.25 * pregrasp_ready + 0.15 * max(0.0, 1.0 - distance)))
        state_estimate = dict(fallback.state_estimate)
        state_estimate.setdefault("grasp_confidence", heuristic_confidence)
        return InferenceResult(
            task_phase=fallback.task_phase,
            state_estimate=state_estimate,
            reward_hints=dict(fallback.reward_hints),
            anomalies=list(fallback.anomalies),
            visual_summary=dict(fallback.visual_summary),
            notes=list(fallback.notes),
        )

    def _live_mode_enabled(self) -> bool:
        cfg = self.config or {}
        return bool(cfg.get("live_inference", False) or cfg.get("use_live_model", False))

    def _build_live_prompt(
        self,
        observation: Observation,
        repository_context: dict[str, Any],
        metadata: dict[str, Any],
        fallback: InferenceResult,
    ) -> str:
        target_label = str(observation.metadata.get("target_object_label", metadata.get("task_name", "target_object")))
        dash_detections = next((camera.detections for camera in observation.cameras if camera.role == "dash"), [])
        compact_detections = [
            {
                "label": str(item.get("label", "object")),
                "confidence": round(float(item.get("confidence", 0.0)), 3),
                "is_target": bool(item.get("is_target", False)),
            }
            for item in dash_detections[:3]
        ]
        sensors = observation.sensors
        compact_sensors = {
            "object_distance": round(float(sensors.get("object_distance", 0.0)), 3),
            "heading_error_deg": round(float(sensors.get("heading_error_deg", 0.0)), 2),
            "claw_alignment": round(float(sensors.get("claw_alignment", 0.0)), 3),
            "pregrasp_ready": round(float(sensors.get("pregrasp_ready", 0.0)), 3),
            "target_reachable": round(float(sensors.get("target_reachable", 0.0)), 3),
            "target_object_visible": round(float(sensors.get("target_object_visible", 0.0)), 3),
            "collision_risk": round(float(sensors.get("collision_risk", 0.0)), 3),
            "battery_level": round(float(sensors.get("battery_level", 1.0)), 3),
            "object_grasped": round(float(sensors.get("object_grasped", 0.0)), 3),
        }
        compact_state = {
            "task_phase": fallback.task_phase,
            "grasp_confidence": round(float(fallback.state_estimate.get("grasp_confidence", 0.0)), 3),
        }
        schedule_notes = list(repository_context.get("action_scheme", {}).get("schedule_notes", []))[:2]
        constraints = list(((self.profile or {}).get("llm", {}).get("task", {}) or {}).get("constraints", []))[:2]
        return (
            f"Target object: {target_label}. "
            f"Goal: {metadata.get('task_goal', 'complete the task safely')}.\n"
            f"Allowed phases: approach, pregrasp, grasp, hold, stabilize.\n"
            f"Current state: {compact_state}. Sensors: {compact_sensors}.\n"
            f"Visible objects: {compact_detections}.\n"
            f"Action scheme: {repository_context.get('action_scheme', {}).get('name', 'direct_channel_control')}. Notes: {schedule_notes}.\n"
            f"Constraints: {constraints}.\n"
            "Return JSON only with keys task_phase, grasp_confidence, target_object, heading_bias_deg, reward_hints, anomalies, notes."
        )

    def _resolve_live_decision(self, live_prompt: str, observation: Observation, fallback: InferenceResult):
        if not self._live_mode_enabled():
            return request_ollama_decision(prompt=live_prompt, provider_cfg=self.config, fallback=fallback)
        signature = self._observation_signature(observation, fallback)
        if self._cached_signature == signature and self._cached_decision is not None and self._cached_uses_remaining > 0:
            self._cached_uses_remaining -= 1
            return self._cached_decision
        decision = request_ollama_decision(prompt=live_prompt, provider_cfg=self.config, fallback=fallback)
        if decision is not None and decision.used_live_model:
            self._cached_signature = signature
            self._cached_decision = decision
            self._cached_uses_remaining = int((self.config or {}).get("decision_cache_reuse_steps", 2))
        else:
            self._cached_signature = None
            self._cached_decision = None
            self._cached_uses_remaining = 0
        return decision

    def _observation_signature(self, observation: Observation, fallback: InferenceResult) -> str:
        sensors = observation.sensors
        dash_detections = next((camera.detections for camera in observation.cameras if camera.role == "dash"), [])
        target_label = str(observation.metadata.get("target_object_label", "target_object"))
        top_labels = [str(item.get("label", "object")) for item in dash_detections[:3]]
        parts = [
            target_label,
            fallback.task_phase,
            f"d={float(sensors.get('object_distance', 0.0)):.2f}",
            f"a={float(sensors.get('claw_alignment', 0.0)):.2f}",
            f"p={float(sensors.get('pregrasp_ready', 0.0)):.1f}",
            f"r={float(sensors.get('target_reachable', 0.0)):.1f}",
            f"g={float(sensors.get('object_grasped', 0.0)):.1f}",
            f"c={float(sensors.get('collision_risk', 0.0)):.1f}",
            ",".join(top_labels),
        ]
        return "|".join(parts)
