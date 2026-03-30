# Developer Guide

This page is for developers extending, testing, or maintaining `IronEngine-RL`. It complements the architecture and customization pages with workflow-oriented guidance.

## Development Goals

When you change the framework, try to preserve these design goals:

- keep the runtime contracts explicit and stable
- keep safety enforcement outside the model whenever possible
- keep the default repository lightweight, with persistence as an opt-in plugin path
- prefer additive naming layers and metadata instead of breaking public runtime types
- keep profiles readable enough that users can inspect them without reading the full source tree

## Recommended Developer Reading Order

1. `README.md` for the project overview and onboarding paths
2. `docs/framework-architecture.md` for the system shape
3. `docs/api-reference.md` for the main runtime APIs and extension contracts
4. `docs/customization.md` for profile and plugin patterns
5. `docs/examples-and-workflows.md` for concrete starting points

## Source Tree Guide for Developers

### Main Framework Code

- `src/ironengine_rl/interfaces/` - core datamodels and contract definitions
- `src/ironengine_rl/framework/` - manifests, validation, compatibility, and runtime factories
- `src/ironengine_rl/core/` - orchestrator, repository, safety, and agent runtime helpers
- `src/ironengine_rl/inference/` - provider selection and trainable or prompt-driven wrappers
- `src/ironengine_rl/evaluations/` - tasks, metrics, and evaluation suite assembly
- `src/ironengine_rl/platforms/` - hardware and simulation platform adapters
- `src/ironengine_rl/plugins/` - plugin loader utilities

### Profiles, Examples, and Plugins

- `profiles/` - canonical reusable profiles for validation, tests, and scaffolding baselines
- `examples/` - runnable reference configurations for hardware and inference workflows
- `user_modules/examples/` - example plugin implementations grouped by capability
- `tests/` - regression coverage for manifests, profiles, plugin loading, and runtime behavior

## Typical Developer Workflows

### 1. Add a New Plugin Module

Choose the right folder first:

- `user_modules/examples/inference/` for providers
- `user_modules/examples/agents/` for agents
- `user_modules/examples/metrics/` for metrics
- `user_modules/examples/safety/` for safety policies
- `user_modules/examples/repositories/` for repository integrations
- `user_modules/examples/update/` for update strategies
- `user_modules/examples/tasks/` for evaluation task builders

Then wire the module into a profile with a `custom_plugin` block and add at least one focused test showing that the profile validates and the plugin loads.

### 2. Add a New Example Profile

A new example should usually include:

- a clear `hardware` or normalized runtime block
- an explicit `action_scheme` when phases or interfaces matter
- contracts for custom providers or tasks when the defaults are not enough
- a log directory under `logs/examples/...`
- a validation test in `tests/test_framework.py` or a nearby focused test file

### 3. Extend a Runtime Surface

If you add a new concept to the framework surface, update all of the following when relevant:

- runtime datamodel or contract definitions
- manifest generation
- validation checks
- scaffold output if the concept is user-facing
- docs and at least one example profile
- tests that protect the new behavior

## Validation and Test Workflow

### Fast Documentation and Profile Checks

Use these commands from an active environment:

```powershell
python -m ironengine_rl.validate --profile examples\hardware\armsmart\profile.mock.json --strict
python -m ironengine_rl.describe --profile profiles\framework_customizable\profile.json
```

### Run the Main Framework Tests

```powershell
python -m unittest tests.test_framework -v
```

When changing only one example or plugin family, prefer adding or running focused tests first before broader runs.

## Developer Guidance for Extension Points

### Inference Providers

A provider should return a valid `InferenceResult` even when optional dependencies are missing. A graceful fallback is often better than making the whole example unreadable or impossible to validate.

The complete ARMSmart PyTorch example follows this rule by using analytic fallback behavior when a weights file or Torch runtime is absent.

### Prompt-Driven Providers

Prompt-driven providers should treat repository notes, action-scheme metadata, and success history as context, but safety-critical enforcement must still remain in the framework safety layer.

### Repositories and Databases

Keep the built-in `KnowledgeRepository` lightweight. If you need persistence, experiment tracking, indexing, or external database integration, implement that as a repository plugin instead of making the default runtime heavier for every user.

### Update Strategies

Use update strategies for trainable or adaptive policies where reward and state feedback legitimately change weights or control parameters. Do not pretend that a hosted or already-trained LLM is applying online weight updates unless you are actually implementing such a mechanism in a custom provider.

## Documentation Expectations

When you add or change framework capabilities, update the docs proactively:

- `README.md` for user-visible starting paths
- `docs/index.md` for docs navigation
- `docs/api-reference.md` when the public API surface changes
- `docs/customization.md` and `docs/plugins-and-extensions.md` for extension patterns
- `docs/examples-and-workflows.md` when new examples are added

## Contribution Checklist

Before considering a change complete, verify:

- the relevant profiles validate
- new or changed plugins load correctly
- tests cover the new behavior
- docs explain the new user-facing configuration
- example paths remain consistent with the actual repository layout

## High-Value Example Patterns

If you want developer-oriented reference material, these are currently the most useful examples to study:

- `examples/plugins/persistent_repository/profile.json` for opt-in persistence
- `examples/inference/armsmart_pytorch_complete/profile.json` for a full custom adaptive pipeline
- `examples/inference/armsmart_ollama_complete/profile.json` for local LLM planning with repository context
- `examples/inference/armsmart_cloud_complete/profile.json` for cloud LLM planning with repository context

## Next Docs to Consult

- `docs/api-reference.md` for symbols and runtime APIs
- `docs/customization.md` for profile examples
- `docs/plugins-and-extensions.md` for plugin layout
- `docs/logging-and-outputs.md` for run artifacts and repository files