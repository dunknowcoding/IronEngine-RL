# Profiles and Configuration

Profiles are the main user-facing configuration surface in `IronEngine-RL`. They describe the runtime mode, platform, sensors, safety limits, inference backend, repository behavior, evaluation wiring, and—when LLM-backed inference is used—the user task and role-contract path.

## Main Idea

Instead of hiding wiring across code files, `IronEngine-RL` keeps most setup visible in the profile. This makes it easier to audit what the robot expects, what the model sees, and how the framework enforces boundaries.

## Core Sections

Typical sections include:

- `runtime` - simulation, mock, HIL, or hardware mode
- `platform` or grouped `hardware` - platform and interface capabilities
- `simulator` - world, object, and fault-model configuration for simulation
- `vision` - camera backend, IDs, replay files, or synthetic camera settings
- `safety` - chassis, arm, battery, and stale-observation limits
- `model_provider` - built-in or custom inference backend
- `agent` - action-selection logic
- `repository` - transition logging and optional persistence
- `evaluation` - task definition and metrics
- `action_scheme` - command channels, feedback fields, result fields, and scheduling notes
- `llm` - role-contract and user mission for LLM-backed inference

## How to Set a User Task for an LLM

When the backend is prompt-driven or LLM-style, the user should set the mission in the `llm` block.

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "right_object_grasp",
      "goal": "Grasp the right object on the work surface and avoid non-target objects.",
      "success_criteria": [
        "keep the correct target selected",
        "enter pregrasp only when the target is aligned and reachable"
      ],
      "constraints": [
        "respect the action scheme",
        "do not bypass safety enforcement"
      ]
    }
  }
}
```

This is the preferred place for user intent. Avoid burying the task only inside `system_prompt`; the framework can reason about `llm.task`, validate it, and include it consistently in prompt composition.

## Minimal Editing Workflow

1. start from a profile in `profiles/` or `examples/`
2. set runtime and platform details
3. configure safety limits and sensors
4. choose the inference backend in `model_provider`
5. if the backend is LLM-backed, set `llm.role_contract_file` and `llm.task`
6. validate before strict execution
7. run a mock or simulation path before hardware bring-up

## `profiles/` versus `examples/`

- `profiles/` contains reusable reference baselines for validation, scaffolding, and standard contracts
- `examples/` contains runnable scenario-driven profiles that demonstrate complete workflows

## Notes for LLM-backed Profiles

For LLM-backed profiles, the most important fields are:

- `llm.role_contract_file` - usually `SOUL.md`
- `llm.task` - the user mission
- `model_provider.type` - for example `ollama_prompt`, `cloud_prompt`, or a custom LLM-style plugin
- `action_scheme` - explicit control channels and schedule notes that the prompt can reference

## Validation

`build_validation_report(profile)` validates these fields and warns when a custom role-contract path is missing. Scaffolded LLM profiles also include a starter `llm.task` placeholder so users know where to add the mission immediately.

## Related Pages

- `docs/llm-task-and-soul.md` for the dedicated LLM task workflow
- `docs/examples-and-workflows.md` for runnable example paths
- `docs/customization.md` for custom providers and contracts
- `README.md` for the main quick-start overview
## Task-Setting Checklist

When you set a task in a profile, update these parts together:

1. `llm.role_contract_file` - usually `SOUL.md`
2. `llm.task.name` - stable mission identifier
3. `llm.task.goal` - plain-language objective
4. `llm.task.success_criteria` - observable completion conditions
5. `llm.task.constraints` - safety and workflow limits
6. `llm.task.output_requirements` - optional response-shape guidance
7. `evaluation.task` - metric/evaluation wiring
8. `action_scheme` - allowed control surface and schedule notes

A good rule is: keep the user mission in `llm.task`, keep framework scoring in `evaluation.task`, and keep control limits in `action_scheme` plus `safety`. 
## Full Task-Oriented Profile Fragment

This example shows the most common task-related settings together in one profile fragment.

```json
{
  "model_provider": {
    "type": "ollama_prompt",
    "model": "qwen3.5:2b",
    "base_url": "http://127.0.0.1:11434",
    "timeout_s": 20.0
  },
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "multi_object_target_grasp",
      "goal": "Pick up the red mug on the right side of the table and ignore the blue box and green bottle.",
      "success_criteria": [
        "keep the red mug selected during approach",
        "enter pregrasp only when the target is aligned and reachable",
        "finish the grasp without violating safety limits"
      ],
      "constraints": [
        "respect the action scheme",
        "do not bypass the safety controller",
        "use visible detections and repository context for target selection"
      ],
      "output_requirements": [
        "return the next framework-compatible control phase",
        "ground the decision in current detections"
      ]
    }
  },
  "evaluation": {
    "task": "tabletop_grasp",
    "metrics": ["task_performance", "boundary_violations"]
  },
  "action_scheme": {
    "name": "target_first_grasp_schedule",
    "schedule_notes": [
      "approach before aggressive arm extension",
      "prefer target stability over fast target switching",
      "only enter grasp when alignment and safety are acceptable"
    ]
  },
  "safety": {
    "collision_stop_threshold": 0.8,
    "low_battery_stop_threshold": 0.15,
    "stale_observation_stop_steps": 3
  },
  "repository": {
    "type": "knowledge_repository"
  }
}
```

If you use a different backend such as `cloud_prompt` or a custom LLM-style plugin, keep the `llm` block and task fields the same, then only swap the provider-specific settings in `model_provider`. 
## Runnable Task Example

Use `examples/inference/task_oriented_multi_object_grasp/profile.json` as the compact runnable example for task-oriented LLM settings.

It keeps `live_inference` disabled by default so users can validate task wiring, action-scheme integration, repository context, and evaluation flow before relying on a live local model server.