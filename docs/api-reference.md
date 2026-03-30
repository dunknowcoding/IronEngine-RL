# API Reference

This page explains the main public-facing APIs of `IronEngine-RL` so developers can understand how profiles, runtime components, contracts, and plugins connect together.

## Core Runtime Entry Points

### Profile Loading and Validation

- `ironengine_rl.config.load_profile(path)` - load a JSON profile and normalize grouped hardware fields into the runtime-ready shape
- `ironengine_rl.framework.build_validation_report(profile)` - return schema and compatibility checks used by CLI preflight and strict validation
- `ironengine_rl.framework.build_framework_manifest(profile)` - describe active framework modules, aliases, action scheme, and contracts
- `ironengine_rl.framework.build_active_platform_manifest(profile)` - describe the selected hardware or simulation platform
- `ironengine_rl.framework.build_compatibility_report(profile, framework_manifest, platform_manifest)` - show whether the selected platform and framework modules agree on required contracts

### Runtime Assembly

- `ironengine_rl.framework.factories.build_runtime_components(profile, run_dir=None)` - assemble environment, provider, agent, safety layer, repository, and evaluation suite
- `ironengine_rl.core.RuntimeOrchestrator(profile_path=...)` - run the framework loop for simulation, mock hardware, HIL, or hardware modes
- `ironengine_rl.inference.provider_from_profile(profile)` - build the configured inference provider from built-in or plugin-backed configuration
- `ironengine_rl.evaluations.evaluation_suite_from_profile(profile)` - build the configured task definition plus metrics

## Core Datamodels

The main runtime datamodels live under `src/ironengine_rl/interfaces/models.py`.

### `ActionScheme`

Use `ActionScheme` when you want a profile to explicitly describe the command channels, feedback fields, result fields, and scheduling notes that define the intended control workflow.

Main fields:

- `name` - human-readable schedule or interface name
- `command_channels` - actuator channels expected by the agent and safety layer
- `feedback_fields` - sensor or telemetry fields expected from the robot or simulator
- `result_fields` - result-oriented outputs emphasized for evaluation or downstream tooling
- `schedule_notes` - phase and sequencing notes for developers or prompt-driven providers

### `Observation`

`Observation` contains the current timestamp, sensor values, camera feature frames, and optional metadata.

Key fields and helpers:

- `timestamp_s` - observation time in seconds
- `sensors` - telemetry dictionary used by providers, safety, and evaluation modules
- `cameras` - list of `CameraFrame` values carrying per-camera features or detections
- `feedback` - additive alias for the `sensors` payload

### `InferenceResult`

Providers return `InferenceResult` to communicate task phase, state estimate, reward hints, anomalies, visual summaries, and explanatory notes.

Main fields:

- `task_phase` - high-level phase such as `approach`, `pregrasp`, or `grasp`
- `state_estimate` - derived internal state such as distance, alignment, or readiness scores
- `reward_hints` - values that downstream code can use when shaping reward or debugging performance
- `anomalies` - warning conditions like low battery or collision risk
- `visual_summary` - camera-role summaries produced by the inference layer
- `notes` - developer-facing explanation of model behavior or prompt composition
- `results` - additive alias returning a result-oriented summary view

### `ActionCommand`

Agents return `ActionCommand` values for chassis, arm, wrist, and gripper channels.

Main fields and helpers:

- `chassis_forward`, `chassis_strafe`, `chassis_turn` - chassis motion channels
- `arm_lift`, `arm_extend`, `wrist_yaw`, `gripper_close` - manipulator channels
- `auxiliary` - custom metadata such as selected policy phase or safety hints
- `action_scheme` - additive alias stored inside `auxiliary` so actions can record which schedule they follow
- `command` - additive alias returning a command-oriented summary payload

### `StepResult` and `RewardBreakdown`

The environment returns `StepResult`, which bundles the next observation, reward, done flag, and info payload.

- `RewardBreakdown.total` - scalar reward used for summaries and training-style workflows
- `RewardBreakdown.components` - named reward terms such as `progress`, `alignment`, or `safety`
- `StepResult.results` - additive alias returning feedback, reward totals, reward components, and terminal state in one structure

## Main Ports and Extension Contracts

The framework uses port-style abstractions from `src/ironengine_rl/interfaces/contracts.py` so built-in and custom modules share a stable runtime surface.

Key ports include:

- `ModelProviderPort` - produce `InferenceResult` from `Observation` plus repository context
- `AgentPort` - convert observation and inference into `ActionCommand`
- `SafetyPolicyPort` - constrain or replace unsafe actions before actuation
- `EnvironmentPort` - step the selected simulator or hardware adapter and return `StepResult`
- `KnowledgeRepositoryPort` - record transitions, updates, summaries, and repository context
- `UpdateStrategyPort` - adjust provider weights or internal policy parameters from reward/state context
- `PlatformPort` - expose a hardware or simulation adapter builder for a platform type

## Built-In Module Families

### Inference Providers

Built-in `model_provider.type` values:

- `rule_based` - deterministic heuristic provider
- `linear_policy` - lightweight weighted policy
- `pytorch_trainable` - framework-managed trainable provider scaffold
- `ollama_prompt` - local prompt-driven provider
- `lmstudio_prompt` - local prompt-driven provider for LM Studio style runtimes
- `cloud_prompt` - hosted prompt-driven provider
- `custom_plugin` - load a user-defined provider from `module_path` or `file_path`

### Evaluation

Built-in evaluation task names include:

- `tabletop_grasp`
- `hardware_link_validation`

Built-in metrics include:

- `task_performance`
- `boundary_violations`

Both task definitions and metrics can also be supplied as `custom_plugin` entries.

### Repository Modes

- `knowledge_repository` or `default` - lightweight in-memory repository behavior
- `custom_plugin` - persistent or specialized repository integrations such as JSON storage or external database bridges

## Plugin API Shape

A plugin is typically referenced like this:

```json
{
  "type": "custom_plugin",
  "plugin": {
    "module_path": "user_modules.examples.inference.custom_inference_provider:CustomInferenceProvider"
  }
}
```

The loader accepts:

- `module_path` in the form `package.module:SymbolName`
- `file_path` plus `symbol` when loading from an arbitrary Python file

Internally, plugin loading is handled by `ironengine_rl.plugins.instantiate_plugin(...)`.

## CLI APIs

### Validation

```powershell
python -m ironengine_rl.validate --profile examples\hardware\armsmart\profile.mock.json --strict
```

### Describe a Profile

```powershell
python -m ironengine_rl.describe --profile profiles\framework_customizable\profile.json
```

### Scaffold a New Profile

```powershell
python -m ironengine_rl.scaffold --output profiles\my_robot\profile.json --guided-goal custom_hardware --name my_robot --guided-backend udp --overwrite
```

### Run the Runtime Loop

```powershell
python -m ironengine_rl.cli --profile examples\hardware\armsmart\profile.mock.json --episodes 1 --steps 12
```

## Suggested Reading Order

- read `docs/framework-architecture.md` for the big picture
- read `docs/customization.md` for profile and plugin patterns
- read `docs/plugins-and-extensions.md` for extension layouts
- read `docs/developer-guide.md` for workflow, testing, and contribution guidance
## LLM Task Context

Prompt-driven inference now supports a dedicated role-and-task context layer built from:

- `SOUL.md` - the default LLM role contract
- `llm.task` - the user-defined mission, such as grasping the right object or folding a cloth
- `model_provider.role_contract_file` or `model_provider.task` - optional provider-local overrides

### Helper API

- `src/ironengine_rl/inference/llm_context.py` - resolves the active role contract and the active task goal for LLM-backed inference
- `resolve_role_contract_reference(profile, provider_cfg)` - determine which role-contract file should be used
- `load_role_contract(profile, provider_cfg)` - load the contract text, typically from `SOUL.md`
- `resolve_llm_task(profile, provider_cfg, context=None)` - normalize the active task specification from profile and provider config
- `build_role_and_task_preamble(profile, provider_cfg, context=None)` - build the shared preamble that prompt-driven providers prepend to their prompt

### Profile Shape

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "cloth_fold_and_place",
      "goal": "Fold the cloth neatly and place the folded result into the target tray.",
      "success_criteria": ["align the cloth before the fold"],
      "constraints": ["respect the action scheme and safety layer"]
    }
  }
}
```

### Validation Notes

- `build_validation_report(profile)` now validates `llm.task` and `llm.role_contract_file` when present
- missing custom role-contract paths produce a warning and fall back to the built-in SOUL text
- scaffolded `local_ollama` and `cloud_api` profiles now include a default `llm.task` placeholder plus `SOUL.md` reference
### User-Facing Task Entry Point

For LLM-backed inference, the main user entry point is the `llm` section in the profile:

- `llm.role_contract_file` - points to `SOUL.md`
- `llm.task` - defines the user mission
- `model_provider.task` - optional provider-local override

This is the preferred API surface for task-oriented prompting because it is structured, validated, and visible to the framework manifest.