# Examples and Workflows

This page collects the main runnable profiles and plugin examples for `IronEngine-RL`, then arranges them into a low-risk onboarding path so users can introduce hardware, inference, and persistence one layer at a time.

## `profiles/` and `examples/`

Use `profiles/` when you want reusable framework baselines. Those files are the canonical reference inputs for validation, tests, scaffolding, and understanding the standard runtime contract without extra scenario-specific wiring.

Use `examples/` when you want runnable demonstrations of a complete path, such as ARMSmart mock hardware, custom PyTorch reasoning, local/cloud LLM integration, repository/database persistence, or anomaly routing customization.

In practice, users usually validate or inspect a baseline profile first, then run the nearest example profile, and only after that copy the closer file into their own custom deployment profile.

## Hardware Examples

- `examples/hardware/armsmart/profile.mock.json` - mock validation path for ARMSmart
- `examples/hardware/armsmart/profile.hil.json` - hardware-in-the-loop ARMSmart configuration
- `examples/hardware/custom_robots/template.profile.json` - blank grouped-hardware template for new robots
- `examples/hardware/custom_robots/udp_mobile_manipulator.profile.json` - wheeled manipulator example
- `examples/hardware/custom_robots/visionless_link_monitor.profile.json` - no-camera telemetry example
- `examples/hardware/custom_robots/multi_camera_sensor.profile.json` - extra camera and sensor example
- `examples/hardware/custom_robots/multi_sensor_station.profile.json` - grouped multi-sensor example covering depth cameras, LiDAR, ranging, IMU, environment, gesture, pressure, and audio-derived signals
- `examples/hardware/custom_robots/multi_sensor_guarded.profile.json` - guarded multi-sensor example with a custom safety policy, sensor-health metric, and named mock scenarios for nominal, front-range stop, gesture stop, and air-quality warning paths

## Inference Examples

- `examples/inference/armsmart_ollama/profile.json` - local Ollama backend
- `examples/inference/armsmart_ollama_complete/profile.json` - complete local LLM example with repository/database context, custom task wiring, and action-scheme notes
- `examples/inference/armsmart_cloud_api/profile.json` - hosted API backend
- `examples/inference/armsmart_cloud_complete/profile.json` - complete cloud LLM example with repository/database context, custom task wiring, and action-scheme notes
- `examples/inference/armsmart_pytorch_custom/profile.json` - custom PyTorch provider
- `examples/inference/armsmart_pytorch_complete/profile.json` - complete custom PyTorch stack with custom provider, custom update strategy, custom task, custom metric, custom agent, and persistent repository

## Plugin and Repository Examples

- `examples/plugins/persistent_repository/profile.json` - additive `action_scheme` plus persistent repository plugin example
- `examples/plugins/anomaly_customization/profile.json` - anomaly-focused simulation example with custom anomaly labels and safety routing
- `user_modules/examples/repositories/persistent_json_repository.py` - opt-in repository plugin that persists transitions and summaries to JSON
- `user_modules/examples/repositories/armsmart_experiment_repository.py` - richer repository/database example that keeps reward, state, and policy traces for ARMSmart experiments
- `user_modules/examples/update/armsmart_reward_blend_update.py` - custom policy and weight update rule example for adaptive PyTorch workflows
- `user_modules/examples/tasks/armsmart_pick_place_task.py` - custom ARMSmart real-task definition example
- `user_modules/examples/inference/anomaly_aware_inference_provider.py` - custom provider example that emits configurable anomaly labels
- `user_modules/examples/safety/anomaly_routing_policy.py` - custom safety policy example that converts anomaly labels into warning-only or stop behavior
- `user_modules/examples/safety/multi_sensor_guard_policy.py` - custom safety policy example for front-range, gesture-stop, air-quality, and thermal warnings
- `user_modules/examples/metrics/sensor_health_metric.py` - custom metric example for tracking front-range, air-quality, gesture-stop, and battery-health alerts

## Recommended Onboarding Path

1. inspect or validate a baseline in `profiles/` first
2. choose the nearest runnable scenario in `examples/`
3. confirm transport, telemetry, safety behavior, anomaly expectations, and the intended action scheme
4. inspect runtime logs, summaries, and repository outputs
5. move to HIL or real hardware only after the mock path is stable
6. only then swap inference backends or persistence plugins if needed
7. use `examples/inference/armsmart_pytorch_complete/profile.json` when you want a single example that ties together policy updates, weight updates, reward/state tracking, database persistence, and a custom ARMSmart task
8. use `examples/inference/armsmart_ollama_complete/profile.json` or `examples/inference/armsmart_cloud_complete/profile.json` when you want repository-aware local or cloud LLM planning examples
9. use `examples/plugins/anomaly_customization/profile.json` when you want to experiment with custom anomaly labels and safety routing before introducing real hardware
10. use `examples/hardware/custom_robots/multi_sensor_station.profile.json` when you want a copyable grouped-hardware pattern for sensor-rich robots without starting from a blank template
11. use `examples/hardware/custom_robots/multi_sensor_guarded.profile.json` when you want a sensor-rich mock-safe profile that already demonstrates custom guard-policy reactions, sensor-health evaluation, and named mock scenarios you can switch between immediately

## Scaffold First Option

If you are starting from scratch, run `ironengine_rl.scaffold` first. The scaffold now emits an `action_scheme` block automatically so the generated profile already shows command channels, feedback fields, result fields, and scheduling notes.

For the complete PyTorch example, you can optionally create demo weights with `python examples\inference\armsmart_pytorch_complete\generate_demo_weights.py`. The profile still runs without that file because the provider falls back to an analytic policy when weights are absent.

## Related Pages

- `docs/repository-layout.md` for the repository structure and the role of `profiles/`
- `docs/profiles-and-configuration.md` for profile editing guidance
- `docs/examples-matrix.md` for cross-example feature comparison
- `docs/anomaly-detection-and-safety.md` for anomaly-specific customization patterns
- `docs/customization.md` for profile and plugin design patterns
- `docs/plugins-and-extensions.md` for extension-point organization
- `docs/logging-and-outputs.md` for expected runtime artifacts
## Verified Custom-Model Example Path

For customized-model work, the recommended path is now:

1. start from `examples/inference/armsmart_pytorch_custom/profile.json` if you only need a minimal plugin pattern
2. move to `examples/inference/armsmart_pytorch_complete/profile.json` when you need weight adaptation, repository traces, and a custom task
3. generate demo weights with `python examples\inference\armsmart_pytorch_complete\generate_demo_weights.py` when you want the PyTorch model path instead of fallback-only behavior
4. run `python tools\run_armsmart_pytorch_grasp_trial.py` to validate the full `approach -> pregrasp -> grasp_or_lift` process
5. inspect `grasp_trial_report.json`, `summary.json`, and `armsmart_experiment_db.json` in the fresh run directory under `logs/examples/inference/armsmart_pytorch_complete/`

### What to verify in the outputs

- `Weights loaded: True` in provider notes when the demo weights file is present
- `adaptive_pregrasp_weight` and related adaptive fields changing across steps
- `policy_trace` recording `approach`, `pregrasp`, and `grasp_or_lift`
- `action_scheme` staying aligned with `armsmart_pick_place_schedule`

See `examples/inference/armsmart_pytorch_complete/grasp_process.md` for the compact walkthrough.
## Task-Oriented LLM Example Path

If the user wants to set a concrete task for an LLM-backed robot workflow, use this sequence:

1. copy a local or cloud LLM example profile
2. set `llm.role_contract_file` to `SOUL.md`
3. define the mission in `llm.task`
4. validate the profile
5. run the example and inspect the repository summary to confirm the task was followed

For example, in a multi-object grasping setup, the user should put the target-object instruction in `llm.task.goal` instead of hiding it only inside `system_prompt`.