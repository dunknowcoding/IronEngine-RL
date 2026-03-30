from __future__ import annotations

from typing import Any

from ironengine_rl.inference.llm_context import DEFAULT_ROLE_CONTRACT_FILE
from ironengine_rl.inference.prompt_driven import CloudPromptProvider, LMStudioPromptProvider, OllamaPromptProvider
from ironengine_rl.inference.trainable import PyTorchTrainableProvider
from ironengine_rl.model_providers.linear_policy import LinearPolicyProvider
from ironengine_rl.model_providers.rule_based import RuleBasedModelProvider
from ironengine_rl.plugins import describe_plugin_spec, instantiate_plugin
from ironengine_rl.training import describe_available_update_strategies


def provider_from_profile(profile: dict[str, Any]):
    provider_cfg = profile.get("model_provider", {})
    provider_type = provider_cfg.get("type", "rule_based")
    if provider_type == "custom_plugin":
        return instantiate_plugin(provider_cfg.get("plugin", {}), profile=profile, config=provider_cfg)
    if provider_type == "rule_based":
        return RuleBasedModelProvider()
    if provider_type in {"custom_model", "linear_policy"}:
        return LinearPolicyProvider(profile)
    if provider_type == "pytorch_trainable":
        return PyTorchTrainableProvider(profile)
    if provider_type == "ollama_prompt":
        return OllamaPromptProvider(profile, provider_cfg)
    if provider_type == "lmstudio_prompt":
        return LMStudioPromptProvider(profile, provider_cfg)
    if provider_type == "cloud_prompt":
        return CloudPromptProvider(profile, provider_cfg)
    raise ValueError(f"Unsupported model provider: {provider_type}")


def describe_available_inference_modules() -> dict[str, Any]:
    return {
        "rule_based": {
            "style": "heuristic_or_rules",
            "description": "Deterministic baseline controller encoded directly in framework rules.",
            "config": {},
        },
        "linear_policy": {
            "style": "trainable_weights",
            "description": "Configurable linear policy that shares framework-managed weights.",
            "config": {
                "weights_file": "path",
                "grasp_threshold": "float",
            },
        },
        "pytorch_trainable": {
            "style": "trainable_weights",
            "description": "Custom trainable provider scaffold designed for user PyTorch models with pluggable update strategies.",
            "config": {
                "weights_file": "path",
                "grasp_threshold": "float",
                "torch_device": "str",
                "update_strategy": describe_available_update_strategies(),
            },
        },
        "ollama_prompt": {
            "style": "prompt_engineering",
            "description": "Uses an Ollama-hosted local model through prompt engineering and framework safety constraints.",
            "config": {
                "model": "str",
                "base_url": "str",
                "system_prompt": "str",
                "prompt_template": "str",
                "role_contract_file": DEFAULT_ROLE_CONTRACT_FILE,
                "task": {
                    "name": "str",
                    "goal": "str",
                    "success_criteria": ["str"],
                    "constraints": ["str"],
                },
                "timeout_s": "float",
            },
        },
        "lmstudio_prompt": {
            "style": "prompt_engineering",
            "description": "Uses an LM Studio local model through prompt engineering and structured response conventions.",
            "config": {
                "model": "str",
                "base_url": "str",
                "system_prompt": "str",
                "prompt_template": "str",
                "role_contract_file": DEFAULT_ROLE_CONTRACT_FILE,
                "task": {
                    "name": "str",
                    "goal": "str",
                    "success_criteria": ["str"],
                    "constraints": ["str"],
                },
                "timeout_s": "float",
            },
        },
        "cloud_prompt": {
            "style": "prompt_engineering",
            "description": "Uses a cloud API provider with explicit prompt templates, temperature, and schema constraints.",
            "config": {
                "model": "str",
                "api_base": "str",
                "api_key_env": "str",
                "system_prompt": "str",
                "role_contract_file": DEFAULT_ROLE_CONTRACT_FILE,
                "task": {
                    "name": "str",
                    "goal": "str",
                    "success_criteria": ["str"],
                    "constraints": ["str"],
                },
                "temperature": "float",
                "timeout_s": "float",
            },
        },
        "custom_plugin": {
            "style": "custom",
            "description": "Loads a user-defined inference provider from a Python module or file.",
            "config": {
                "plugin": describe_plugin_spec({}),
            },
        },
    }
