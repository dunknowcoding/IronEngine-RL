# Plugins and Extensions

## Canonical Plugin Layout

Place custom or example plugins under:

- `user_modules/examples/inference/`
- `user_modules/examples/agents/`
- `user_modules/examples/metrics/`
- `user_modules/examples/safety/`
- `user_modules/examples/repositories/`
- `user_modules/examples/update/`
- `user_modules/examples/tasks/`

Compatibility wrapper modules remain in `user_modules/examples/` for older import paths.

## Common Extension Points

- inference providers
- agents
- safety policies
- evaluation tasks and metrics
- update strategies
- repositories
- evaluation task builders

## Module Path Example

```json
{
  "type": "custom_plugin",
  "plugin": {
    "module_path": "user_modules.examples.inference.custom_inference_provider:CustomInferenceProvider"
  }
}
```

## File Path Example

```json
{
  "type": "custom_plugin",
  "plugin": {
    "file_path": "user_modules/custom_provider.py",
    "symbol": "CustomProvider"
  }
}
```

## Persistent Repository Example

```json
{
  "repository": {
    "type": "custom_plugin",
    "plugin": {
      "module_path": "user_modules.examples.repositories.persistent_json_repository:PersistentJsonRepository"
    },
    "database_file": "repository_database.json"
  }
}
```

Use the built-in `KnowledgeRepository` for default lightweight runs. Use a repository plugin only when you want persisted transitions, richer audit trails, or an integration point for external indexing or database workflows.

## Anomaly Customization Example

The repository now also includes an anomaly-routing example built from a custom provider plus a custom safety policy:

- `user_modules/examples/inference/anomaly_aware_inference_provider.py` - emits configurable anomaly labels from visibility, battery, collision, and fault-window conditions
- `user_modules/examples/safety/anomaly_routing_policy.py` - stops on selected anomalies and leaves others as warnings
- `examples/plugins/anomaly_customization/profile.json` - runnable profile that wires those two pieces together

## Complete ARMSmart Example Modules

- `user_modules/examples/inference/armsmart_adaptive_torch_provider.py` - adaptive PyTorch-style provider with repository-aware update hooks
- `user_modules/examples/inference/armsmart_local_llm_provider.py` - local LLM provider that composes repository, database, and action-scheme context into prompts
- `user_modules/examples/inference/armsmart_cloud_llm_provider.py` - cloud LLM provider that composes repository, database, and action-scheme context into prompts
- `user_modules/examples/update/armsmart_reward_blend_update.py` - policy and weight update rule example
- `user_modules/examples/tasks/armsmart_pick_place_task.py` - custom ARMSmart pick-and-place task definition
- `user_modules/examples/repositories/armsmart_experiment_repository.py` - persistent experiment repository with reward/state/policy traces

## Related Pages

- `docs/customization.md` for profile and contract customization patterns
- `docs/anomaly-detection-and-safety.md` for the anomaly-routing workflow
- `docs/examples-and-workflows.md` for runnable example paths