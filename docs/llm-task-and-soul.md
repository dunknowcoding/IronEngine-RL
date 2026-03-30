# LLM Tasks and SOUL.md

This page explains how users define an explicit task for LLM-backed inference and how `SOUL.md` is injected into every prompt so the model behaves like a task-oriented reasoning module instead of a generic assistant.

## Why `SOUL.md` Exists

`SOUL.md` is the required default role contract for LLM prompting in `IronEngine-RL`. It tells the model what role it is playing, how it should interpret observations and repository context, and which framework boundaries it must never bypass.

In practice, each prompt should combine:

1. `SOUL.md`
2. the user task from `llm.task`
3. action-scheme and repository context
4. the current observation and detections

## How Users Set a Task

Users set the mission in the profile, not inside ad-hoc prompt text. The main field is `llm.task`.

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "right_object_grasp",
      "goal": "Grasp the right object on the work surface and avoid non-target objects.",
      "success_criteria": [
        "track the target object during approach",
        "move to pregrasp only when alignment and reachability are acceptable",
        "complete the grasp without violating safety limits"
      ],
      "constraints": [
        "respect the action scheme",
        "do not bypass the safety controller"
      ],
      "output_requirements": [
        "return a framework-compatible control phase",
        "keep target selection grounded in visible detections"
      ]
    }
  }
}
```

## Task Fields

- `name` - a stable short identifier for the mission
- `goal` - the plain-language objective the model must pursue
- `success_criteria` - concrete conditions the model should keep in mind while reasoning
- `constraints` - rules that narrow behavior and preserve workflow/safety alignment
- `output_requirements` - optional instructions describing the expected decision style

## `llm.task` versus `evaluation.task`

These fields serve different purposes:

- `llm.task` tells the LLM what mission it is solving during inference
- `evaluation.task` tells the framework how the runtime should measure or interpret the broader evaluation workflow

A common pattern is to keep `evaluation.task` as `tabletop_grasp` while setting `llm.task.goal` to something more specific such as "grasp the red mug on the right side of the table."

## Provider Overrides

Most users should set the task in the top-level `llm` block. Provider-level overrides are available when a specific model backend needs a local task or a different role-contract path:

```json
{
  "model_provider": {
    "type": "ollama_prompt",
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "cloth_fold_and_place",
      "goal": "Fold the cloth neatly and place it into the tray."
    }
  }
}
```

## Examples

### Multi-object grasping

Use `llm.task` to make the target explicit:

- target object: `red_mug`
- distractors: `blue_box`, `green_bottle`
- expected behavior: approach the target, ignore distractors, then transition through `pregrasp` and `grasp` only when the target is aligned and reachable

### Cloth folding

Use `llm.task` to define fold quality and final placement:

- align the cloth
- perform the fold sequence safely
- place the folded result into the correct tray

## Scaffold Behavior

Profiles scaffolded with guided goals such as `local_ollama` and `cloud_api` include a default `SOUL.md` reference and a task placeholder so users know exactly where to describe the mission.

## Recommended User Workflow

1. scaffold or copy a profile close to your scenario
2. set `llm.role_contract_file` to `SOUL.md`
3. define the mission in `llm.task`
4. validate the profile
5. run the example or runtime loop
6. inspect repository notes, metrics, and summaries to confirm the task is being followed

## Related Pages

- `README.md` for the main quick-start path
- `docs/profiles-and-configuration.md` for profile editing guidance
- `docs/customization.md` for plugin and prompt customization patterns
- `docs/api-reference.md` for the helper APIs behind role/task resolution
## Task-Related Settings Checklist

When you configure a task, review these settings together:

- `llm.role_contract_file` - role definition for prompt behavior, usually `SOUL.md`
- `llm.task` - user mission text and reasoning constraints
- `model_provider.type` - the backend that will consume the task
- `model_provider.task` - optional provider-local override when required
- `evaluation.task` - framework evaluation wiring and metrics
- `action_scheme` - allowed control channels and schedule notes
- `safety` or `boundary_conditions` - hard runtime limits that the task must never override
- `repository` - persistent context that can help keep task progress consistent across steps
## Copyable Task Patterns

### Multi-object grasping profile fragment

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "multi_object_target_grasp",
      "goal": "Pick up the red mug on the right side of the table and ignore the blue box and green bottle.",
      "success_criteria": [
        "keep the red mug selected as the target during approach",
        "do not switch to distractor objects when detections fluctuate",
        "enter pregrasp only when the target is aligned and reachable"
      ],
      "constraints": [
        "respect the action scheme",
        "do not bypass the safety controller",
        "use visible detections and repository context for target selection"
      ],
      "output_requirements": [
        "return a framework-compatible control phase",
        "keep the target-choice explanation grounded in current detections"
      ]
    }
  },
  "evaluation": {
    "task": "tabletop_grasp"
  }
}
```

### Cloth-folding profile fragment

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "cloth_fold_and_place",
      "goal": "Fold the cloth neatly and place it into the right tray.",
      "success_criteria": [
        "align the cloth before folding",
        "complete the fold sequence safely",
        "place the folded cloth into the correct tray"
      ],
      "constraints": [
        "respect the action scheme",
        "stay within motion and safety limits"
      ],
      "output_requirements": [
        "return the next phase in the fold workflow",
        "prefer stable staged actions over abrupt motion changes"
      ]
    }
  }
}
```

### Inspection-route profile fragment

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "inspection_route_followup",
      "goal": "Inspect checkpoint A, then B, then C, and report any anomaly before continuing.",
      "success_criteria": [
        "visit checkpoints in order",
        "pause and report if an anomaly is detected",
        "complete the route without violating safety limits"
      ],
      "constraints": [
        "respect the active action scheme",
        "do not skip anomaly handling",
        "do not continue after a required safety stop"
      ],
      "output_requirements": [
        "return a framework-compatible control phase",
        "keep checkpoint state consistent with repository memory"
      ]
    }
  }
}
```

## How to adapt these patterns

- replace `goal` with the concrete mission for your robot and workspace
- write `success_criteria` in terms of observable conditions the model can reason about
- keep `constraints` strict and operational, especially around safety and action-scheme compliance
- keep `evaluation.task` aligned with the runtime metric path, even if the LLM mission is more specific than the evaluation label