from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ironengine_rl.interfaces import InferenceResult


ALLOWED_TASK_PHASES = {"approach", "pregrasp", "grasp", "hold", "stabilize"}


@dataclass(slots=True)
class OllamaDecision:
    used_live_model: bool
    model: str
    raw_response: str
    parsed: dict[str, Any]
    error: str | None = None


def should_use_live_ollama(provider_cfg: dict[str, Any] | None) -> bool:
    cfg = provider_cfg or {}
    return bool(cfg.get("live_inference", False) or cfg.get("use_live_model", False))


def request_ollama_decision(
    *,
    prompt: str,
    provider_cfg: dict[str, Any] | None,
    fallback: InferenceResult,
) -> OllamaDecision | None:
    cfg = provider_cfg or {}
    if not should_use_live_ollama(cfg):
        return None
    model = str(cfg.get("model", "")).strip()
    if not model:
        return OllamaDecision(used_live_model=False, model="", raw_response="", parsed={}, error="No Ollama model configured.")
    base_url = str(cfg.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
    timeout_s = float(cfg.get("timeout_s", 20.0))
    payload = {
        "model": model,
        "prompt": _decision_prompt(prompt, fallback),
        "stream": False,
        "options": _ollama_options(cfg),
    }
    system_prompt = cfg.get("system_prompt")
    if system_prompt:
        payload["system"] = str(system_prompt)
    request = Request(
        url=f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return OllamaDecision(used_live_model=False, model=model, raw_response="", parsed={}, error=f"HTTP {exc.code} from Ollama")
    except URLError as exc:
        return OllamaDecision(used_live_model=False, model=model, raw_response="", parsed={}, error=f"Ollama connection failed: {exc.reason}")
    except Exception as exc:
        return OllamaDecision(used_live_model=False, model=model, raw_response="", parsed={}, error=f"Ollama request failed: {exc}")

    raw_response = str(body.get("response") or body.get("thinking") or "").strip()
    if not raw_response:
        return OllamaDecision(used_live_model=False, model=model, raw_response="", parsed={}, error="Empty Ollama response.")
    try:
        parsed = _parse_json_response(raw_response)
    except Exception as exc:
        parsed = _parse_loose_control_response(raw_response)
        if not parsed:
            preview = raw_response.replace("\n", " ")[:160]
            return OllamaDecision(used_live_model=False, model=model, raw_response=raw_response, parsed={}, error=f"Invalid Ollama JSON response: {exc}. Preview: {preview}")
    return OllamaDecision(used_live_model=True, model=model, raw_response=raw_response, parsed=parsed)


def apply_ollama_decision(fallback: InferenceResult, decision: OllamaDecision | None) -> InferenceResult:
    if decision is None:
        return fallback
    if not decision.used_live_model:
        notes = list(fallback.notes)
        if decision.error:
            notes.append(f"Ollama live inference unavailable: {decision.error}")
        return InferenceResult(
            task_phase=fallback.task_phase,
            state_estimate=dict(fallback.state_estimate),
            reward_hints=dict(fallback.reward_hints),
            anomalies=list(fallback.anomalies),
            visual_summary=dict(fallback.visual_summary),
            notes=notes,
        )

    parsed = decision.parsed
    task_phase = _normalize_phase(parsed.get("task_phase"), fallback.task_phase)
    grasp_confidence = _clamp_float(parsed.get("grasp_confidence"), _fallback_grasp_confidence(fallback), 0.0, 1.0)
    reward_hints = dict(fallback.reward_hints)
    reward_hints.update(_coerce_numeric_mapping(parsed.get("reward_hints")))
    anomalies = list(dict.fromkeys(list(fallback.anomalies) + _coerce_string_list(parsed.get("anomalies"))))
    state_estimate = dict(fallback.state_estimate)
    state_estimate["grasp_confidence"] = grasp_confidence
    state_estimate["llm_live_inference"] = 1.0
    state_estimate["llm_response_chars"] = float(len(decision.raw_response))
    if "heading_bias_deg" in parsed:
        state_estimate["heading_bias_deg"] = _clamp_float(parsed.get("heading_bias_deg"), 0.0, -45.0, 45.0)
    notes = list(fallback.notes)
    notes.append(f"Live Ollama decision used: {decision.model}")
    if target_object := parsed.get("target_object"):
        notes.append(f"LLM selected target: {target_object}")
    for extra_note in _coerce_string_list(parsed.get("notes"))[:3]:
        notes.append(f"LLM note: {extra_note}")
    return InferenceResult(
        task_phase=task_phase,
        state_estimate=state_estimate,
        reward_hints=reward_hints,
        anomalies=anomalies,
        visual_summary=dict(fallback.visual_summary),
        notes=notes,
    )


def _decision_prompt(prompt: str, fallback: InferenceResult) -> str:
    return (
        f"{prompt}\n\n"
        "Return JSON only with this exact shape:\n"
        '{"task_phase":"approach|pregrasp|grasp|hold|stabilize","grasp_confidence":0.0,"target_object":"label","heading_bias_deg":0.0,"reward_hints":{"alignment_bonus":0.0,"distance_progress":0.0},"anomalies":[],"notes":["brief reason"]}\n'
        f"Use one of these task phases only: {sorted(ALLOWED_TASK_PHASES)}.\n"
        f"Fallback phase if unsure: {fallback.task_phase}.\n"
        "Keep numbers compact and grounded in the observation."
    )


def _parse_json_response(raw_response: str) -> dict[str, Any]:
    if not raw_response:
        return {}
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        parsed = _extract_first_json_object(raw_response)
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def _extract_first_json_object(raw_response: str) -> dict[str, Any]:
    starts = [index for index, char in enumerate(raw_response) if char == "{"]
    for start in starts:
        depth = 0
        for index in range(start, len(raw_response)):
            char = raw_response[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw_response[start : index + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        return parsed
    raise ValueError("no JSON object found in Ollama output")


def _parse_loose_control_response(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if not text:
        return {}
    normalized = text.replace("```json", "").replace("```", "").strip()
    phase_match = re.search(r"\b(approach|pregrasp|grasp|hold|stabilize)\b", normalized, flags=re.IGNORECASE)
    confidence_match = re.search(r"grasp[_\s-]*confidence\D+([0-9]*\.?[0-9]+)", normalized, flags=re.IGNORECASE)
    target_match = re.search(r"target[_\s-]*object\D+([A-Za-z0-9_\-]+)", normalized, flags=re.IGNORECASE)
    heading_match = re.search(r"heading[_\s-]*bias[_\s-]*deg\D+(-?[0-9]*\.?[0-9]+)", normalized, flags=re.IGNORECASE)
    if not any([phase_match, confidence_match, target_match, heading_match]):
        return {}
    parsed: dict[str, Any] = {}
    if phase_match:
        parsed["task_phase"] = phase_match.group(1).lower()
    if confidence_match:
        parsed["grasp_confidence"] = float(confidence_match.group(1))
    if target_match:
        parsed["target_object"] = target_match.group(1)
    if heading_match:
        parsed["heading_bias_deg"] = float(heading_match.group(1))
    parsed.setdefault("notes", ["Parsed from loose local-model output."])
    return parsed


def _ollama_options(cfg: dict[str, Any]) -> dict[str, Any]:
    options = cfg.get("ollama_options", {})
    if not isinstance(options, dict):
        options = {}
    merged = dict(options)
    merged.setdefault("temperature", 0.1)
    merged.setdefault("top_p", 0.9)
    merged.setdefault("num_predict", 96)
    return merged


def _normalize_phase(value: Any, fallback: str) -> str:
    phase = str(value or fallback).strip().lower()
    return phase if phase in ALLOWED_TASK_PHASES else fallback


def _fallback_grasp_confidence(fallback: InferenceResult) -> float:
    state = fallback.state_estimate
    if "grasp_confidence" in state:
        return _clamp_float(state.get("grasp_confidence"), 0.0, 0.0, 1.0)
    if "policy_score" in state:
        return _clamp_float(state.get("policy_score"), 0.0, 0.0, 1.0)
    return _clamp_float(state.get("grasp_ready"), 0.0, 0.0, 1.0)


def _coerce_numeric_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        try:
            result[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return result


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _clamp_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = float(default)
    return max(low, min(high, numeric))
