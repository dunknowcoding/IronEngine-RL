__all__ = ["LinearPolicyProvider", "RuleBasedModelProvider", "provider_from_profile"]


def __getattr__(name: str):
	if name == "provider_from_profile":
		from .base import provider_from_profile

		return provider_from_profile
	if name == "LinearPolicyProvider":
		from .linear_policy import LinearPolicyProvider

		return LinearPolicyProvider
	if name == "RuleBasedModelProvider":
		from .rule_based import RuleBasedModelProvider

		return RuleBasedModelProvider
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
