# Customization Guide

## What You Can Swap

`IronEngine-RL` supports built-in and plugin-loaded modules for inference engines, metrics, agents, safety policies, update strategies, repositories, and platform-specific behaviors.

The recommended plugin layout is now:

- `user_modules/examples/inference/`
- `user_modules/examples/agents/`
- `user_modules/examples/metrics/`
- `user_modules/examples/safety/`
- `user_modules/examples/repositories/`
- `user_modules/examples/update/`
- `user_modules/examples/tasks/`

Older flat paths in `user_modules/examples/` still work through compatibility wrappers.
## Plugin Loading

A plugin can be loaded by Python module path or file path.

### Module Path Example

```json
{
  "type": "custom_plugin",
  "plugin": {
    "module_path": "user_modules.examples.inference.custom_inference_provider:CustomInferenceProvider"
  }
}
```

### File Path Example

```json
{
  "type": "custom_plugin",
  "plugin": {
    "file_path": "user_modules/custom_provider.py",
    "symbol": "CustomProvider"
  }
}
```

The same `custom_plugin` shape is used for `model_provider`, `agent`, `repository`, `boundary_conditions`, evaluation tasks, evaluation metrics, and update strategies.

The complete ARMSmart examples under `examples/inference/armsmart_*_complete/` demonstrate these extension points working together in one profile.

### Repository Plugin Example

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
## Contract Overrides

Use contracts when your deployment intentionally differs from a built-in module's default assumptions.

### Visionless Inference Example

```json
{
  "model_provider": {
    "type": "custom_plugin",
    "plugin": {
      "module_path": "user_modules.examples.inference.visionless_inference_provider:VisionlessInferenceProvider"
    },
    "contract": {
      "observation_fields": ["connection_alive", "battery_level", "collision_risk", "arm_height", "arm_extension"],
      "camera_roles": []
    }
  }
}
```

### Custom Agent and Safety Example

```json
{
  "agent": {
    "type": "custom_plugin",
    "plugin": {
      "module_path": "user_modules.examples.agents.stability_agent:StabilityAgent"
    }
  },
  "boundary_conditions": {
    "type": "custom_plugin",
    "plugin": {
      "module_path": "user_modules.examples.safety.connection_aware_policy:ConnectionAwareSafetyPolicy"
    },
    "contract": {
      "observation_fields": ["connection_alive", "battery_level", "collision_risk"],
      "camera_roles": [],
      "action_channels": ["arm_lift", "arm_extend", "gripper_close"]
    }
  }
}
```

## Additive Aliases and Action Schemes

`IronEngine-RL` keeps the core interface names such as `ActionCommand`, `Observation`, `InferenceResult`, and `StepResult`, but it now exposes additive user-facing aliases:

- `ActionCommand.command` for the command payload view
- `Observation.feedback` for the feedback sensor view
- `InferenceResult.results` and `StepResult.results` for result-oriented views

Use the `action_scheme` block when you want to describe command channels, feedback fields, result fields, and phase notes explicitly without renaming the existing core interfaces.

```json
{
  "action_scheme": {
    "name": "phased_grasp_schedule",
    "command_channels": ["chassis_forward", "chassis_turn", "arm_lift", "arm_extend", "gripper_close"],
    "feedback_fields": ["object_dx", "object_dy", "claw_alignment", "arm_extension", "arm_height"],
    "result_fields": ["reward.total", "reward.components.progress", "done", "info.success"],
    "schedule_notes": [
      "approach before arm extension",
      "close gripper only after alignment exceeds threshold"
    ]
  }
}
```
## Custom Robots and Sensors

You can describe hardware either with explicit `platform.capabilities` plus flat runtime fields or with the grouped `hardware` block. The grouped form is the easiest way to onboard a new robot because it keeps transport, protocol, cameras, safety, and mock telemetry together.

### Recommended Starting Points

- `examples/hardware/custom_robots/template.profile.json` - grouped template for a new robot
- `examples/hardware/custom_robots/udp_mobile_manipulator.profile.json` - wheeled mobile manipulator example
- `examples/hardware/custom_robots/visionless_link_monitor.profile.json` - no-camera telemetry example
- `examples/hardware/custom_robots/multi_camera_sensor.profile.json` - extra camera and custom sensor example

### What to Edit for a New Robot

1. `hardware.platform.capabilities` or `platform.capabilities` - declare the observation fields, camera roles, action channels, and supported transports.
2. `hardware.connection` - choose `mock`, `serial`, `udp`, or another supported transport backend.
3. `hardware.protocol.commands` - map your device's command IDs or protocol constants.
4. `hardware.cameras` - define camera IDs, roles, device indices, and camera backend.
5. `hardware.safety` - set motion and battery limits that must hold even when inference is wrong.
6. `hardware.mock.scenarios` - add realistic telemetry packets so you can validate without hardware attached.

### Sensor Expansion

To add a new sensor such as `force_z`, `temperature_c`, or `lidar_distance`, add it to the platform capability contract and ensure the selected adapter or mock telemetry emits it. Compatibility validation then checks whether inference, safety, and evaluation modules request fields that the platform actually provides.
## ARMSmart as the Complete Reference Integration

Use `examples/hardware/armsmart/` as the canonical hardware reference for `IronEngine-RL`.

- `profile.mock.json` validates the ARMSmart contract without hardware motion
- `profile.hil.json` is the real hardware bring-up template
- `diagnose_mock.ps1` runs a quick PowerShell validation path

### Full ARMSmart Bring-Up

1. Validate `examples/hardware/armsmart/profile.mock.json`.
2. Run the mock profile and inspect `logs/examples/hardware/armsmart/mock`.
3. Tune camera IDs, command IDs, and safety limits while still on mock transport.
4. Move to `examples/hardware/armsmart/profile.hil.json` and replace the serial port and camera backend for the real robot.
5. Only after hardware validation should you swap inference to `examples/inference/armsmart_ollama`, `examples/inference/armsmart_cloud_api`, or `examples/inference/armsmart_pytorch_custom`.

### Custom PyTorch Provider Example

`examples/inference/armsmart_pytorch_custom/profile.json` loads `user_modules.examples.inference.custom_torch_inference_provider:CustomTorchPolicyProvider`, and the helper scripts in that folder train and run a small demonstration network.

`examples/inference/armsmart_pytorch_complete/profile.json` goes further: it combines a custom PyTorch-style provider, a custom update strategy for policy/weight adaptation, a custom ARMSmart task, a custom metric, a custom action-scheme-aware agent, and a persistent repository/database plugin.
### Verified Adaptive PyTorch Workflow

The complete ARMSmart PyTorch example now has a verified companion runner at `tools/run_armsmart_pytorch_grasp_trial.py`.

That runner is the fastest way to confirm that a customized model stack is wired correctly because it checks all of these together:

- a PyTorch-backed provider
- a custom update strategy
- action-scheme-aware agent output
- persistent repository traces
- a concrete grasp process from `approach` to `grasp_or_lift`

### Practical command sequence

```powershell
python examples\inference\armsmart_pytorch_complete\generate_demo_weights.py
python tools\run_armsmart_pytorch_grasp_trial.py
```

### What to inspect after the run

- `grasp_trial_report.json` for step-by-step policy behavior
- `armsmart_experiment_db.json` for `state_trace`, `reward_trace`, and `policy_trace`
- provider notes for weight-loading status and update-strategy name

### Notice

When you are comparing custom model variants, keep the same task, reward scales, and action scheme across runs. Otherwise it becomes hard to tell whether a change came from the model itself or from a changed control contract.
## Validation and Scaffolding

`validation.require_compatibility` enables preflight checks, and `validation.strict` turns compatibility failures into hard errors.

`ironengine_rl.scaffold` now generates an `action_scheme` block automatically so users can see command channels, feedback fields, result fields, and schedule notes directly in the scaffolded profile.

### Useful Commands

```powershell
python -m ironengine_rl.scaffold --output profiles\my_robot\profile.json --guided-goal custom_hardware --name my_robot --guided-backend udp --overwrite
python -m ironengine_rl.scaffold --output profiles\armsmart_ollama_demo\profile.json --guided-goal local_ollama --name armsmart_ollama_demo --overwrite
python -m ironengine_rl.scaffold --output profiles\link_monitor\profile.json --preset visionless_link_monitor --action-scheme-name telemetry_first_schedule --overwrite
python -m ironengine_rl.validate --profile examples\hardware\armsmart\profile.mock.json --strict
python -m ironengine_rl.describe --profile examples\hardware\custom_robots\multi_camera_sensor.profile.json
```

### Guided Goals

- `custom_hardware` - start from the generic template and apply a hardware-friendly preset
- `armsmart_hardware` - choose the ARMSmart mock or HIL reference profile
- `local_ollama` - start from the canonical ARMSmart + Ollama example
- `cloud_api` - start from the canonical ARMSmart + hosted API example
- `custom_pytorch` - start from the canonical ARMSmart + PyTorch example

### Scaffolded `action_scheme` behavior

- command channels are inferred from platform capabilities or plugin contracts
- feedback fields are inferred from platform, inference, evaluation, or boundary contracts
- result fields default to reward and done-oriented outputs
- schedule notes are generated to reflect the preset or guided goal, and you can override the name with `--action-scheme-name`

Use `python -m ...` commands from your active environment so the selected interpreter and installed packages remain consistent across validation, scaffolding, and runtime execution.
## LLM Tasks and `SOUL.md`

Prompt-driven providers and LLM-style custom providers can now consume a dedicated role contract from `SOUL.md` plus a user-defined mission from `llm.task`. This keeps the LLM task-oriented instead of letting it behave like a free-form assistant detached from the robotics workflow.

### Recommended LLM Task Pattern

```json
{
  "llm": {
    "role_contract_file": "SOUL.md",
    "task": {
      "name": "right_object_grasp",
      "goal": "Grasp the right object on the work surface and avoid non-target objects.",
      "success_criteria": [
        "identify the correct target",
        "finish the grasp without violating safety limits"
      ],
      "constraints": [
        "respect the action scheme",
        "do not bypass IronEngine-RL safety boundaries"
      ]
    }
  }
}
```

Use `evaluation.task` for framework evaluation wiring, but use `llm.task` for the user-facing mission you want the LLM to keep in mind during inference.

### Where It Applies

- built-in prompt providers: `ollama_prompt`, `lmstudio_prompt`, and `cloud_prompt`
- custom LLM-style providers such as `user_modules.examples.inference.armsmart_local_llm_provider:ARMSmartLocalLLMProvider`
- scaffolded LLM-oriented profiles created with `guided-goal` values like `local_ollama` and `cloud_api`

See `docs/llm-task-and-soul.md` for the full task-setting workflow and the purpose of `SOUL.md`.
## User Task Setup Checklist

When a user wants an LLM to solve a concrete robotics mission, configure it in this order:

1. keep `SOUL.md` in the repository root
2. point `llm.role_contract_file` to `SOUL.md`
3. write the mission in `llm.task`
4. keep the control surface explicit through `action_scheme`
5. validate the profile before runtime execution

A practical example is a multi-object grasping scenario where the user sets the target object in `llm.task.goal`, then the provider combines that mission with the current detections and schedule notes during prompting.