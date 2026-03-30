# Figure 7.1 Mapping

This page maps the conceptual components in Figure 7.1 to the concrete modules, profiles, and extension points in `IronEngine-RL`. It also points to the most practical example paths for users who want to move from the conceptual diagram to a runnable workflow.

## Core Mapping

| Figure 7.1 concept | IronEngine-RL surface | Where to customize |
| --- | --- | --- |
| Command | `ActionCommand.command` and `action_scheme.command_channels` | profiles, agents, and custom safety plugins |
| Feedback | `Observation.feedback`, `Observation.sensors`, and platform observation fields | hardware profiles, mock telemetry, adapters, and normalized sensor contracts |
| Vision / perception inputs | `Observation.cameras`, `CameraFrame`, and `camera_roles` | camera config, vision backends, and camera-producing sensors such as RGB or depth cameras |
| Results | `InferenceResult.results` and `StepResult.results` | evaluation metrics, logs, repository summaries |
| Knowledge Repository | `KnowledgeRepository` context and summaries | `repository` config or a custom repository plugin |
| Database | optional repository plugin examples and persisted experiment traces | `user_modules/examples/repositories/persistent_json_repository.py` and `user_modules/examples/repositories/armsmart_experiment_repository.py` |
| Action Scheme | additive `action_scheme` config block | profiles such as `examples/plugins/persistent_repository/profile.json` and scaffolded profiles |
| Fast anomaly detection | inference anomalies plus safety and stale-observation checks | safety config, `examples/plugins/anomaly_customization/profile.json`, and custom boundary plugins |
| Policy / weight updating | `model_provider.update_strategy` | built-in or custom update strategy plugins |
| State and reward tracking | observation fields, reward traces, metrics, and repository summaries | custom tasks, metrics, and repository plugins |
| Lightweight runtime path | default in-memory repository and modular adapters | start from mock profiles and add persistence only when needed |
| Local-model practicality | `ollama_prompt`, `lmstudio_prompt`, and compact custom prompt providers | local-model examples and environment-specific model selection |
| Wide platform compatibility | profile-driven adapters plus portable Python runtime layout | transport, camera, and hardware adapter configuration by target OS/platform |

## Where Additional Sensors Integrate

| Sensor family | Recommended integration path | User management path |
| --- | --- | --- |
| Depth camera | `camera_roles` plus `Observation.cameras` | define a dedicated camera role and keep calibration/backend settings in the profile camera block |
| LiDAR and ranging sensors | normalized entries in `Observation.sensors` | expose stable fields such as clearance, obstacle distance, or sector risk in `observation_fields` |
| Temperature, humidity, pressure, air quality | scalar fields in `Observation.sensors` | add the fields to `platform.capabilities.observation_fields`, then attach thresholds or logging rules only where needed |
| IMU | scalar orientation and motion fields in `Observation.sensors` | keep names stable such as `imu_roll_deg`, `imu_pitch_deg`, and `imu_yaw_deg` |
| Gesture inputs | normalized intent or confidence signals in `Observation.sensors` or `metadata` | surface gesture events as readable contract fields instead of binding policy logic directly to a specific device SDK |
| Audio interface | derived scores, events, or metadata | pass wake-word, alarm, speech-confidence, or direction cues through normalized fields or metadata instead of raw audio everywhere |

## Recommended Examples

- `examples/inference/armsmart_pytorch_custom/profile.json` for a custom PyTorch policy provider
- `examples/inference/armsmart_pytorch_complete/profile.json` for a full stack with custom provider, update strategy, task, metric, agent, and repository flow
- `examples/inference/armsmart_ollama_complete/profile.json` for a practical local-model workflow with repository-aware prompt construction
- `examples/inference/armsmart_cloud_complete/profile.json` for a cloud-backed reasoning path using the same runtime contracts
- `examples/plugins/persistent_repository/profile.json` for an additive `action_scheme` plus persistent repository plugin example
- `examples/plugins/anomaly_customization/profile.json` for custom anomaly labels and anomaly-aware safety routing
- `examples/hardware/custom_robots/template.profile.json` for bringing up a new robot interface
- `examples/hardware/custom_robots/multi_sensor_station.profile.json` for a grouped multi-sensor custom hardware contract users can adapt directly

## How the Mapping Helps in Practice

- Use the `Command`, `Feedback`, `Vision / perception inputs`, and `Results` rows to decide what must stay stable when you swap models or hardware.
- Use the `Knowledge Repository` and `Database` rows to keep persistence optional instead of forcing every run into a heavy storage stack.
- Use the `Policy / weight updating` and `State and reward tracking` rows when you need learning-oriented workflows rather than prompt-only reasoning.
- Use the `Local-model practicality` row when you want to experiment with local AI on modest lab machines before committing to larger hardware.
- Use the `Wide platform compatibility` row when the same logical profile must survive different deployment environments.
- Use the additional sensor table when deciding whether a new device belongs in scalar feedback, camera roles, or adapter-specific metadata.

## Design Guidance

Keep the built-in repository lightweight for default runs. Use a custom repository plugin only when you want persistence, external indexing, or richer audit trails.

Use additive aliases instead of replacing core names: `command` complements `ActionCommand`, `feedback` complements `Observation`, and `results` complements `InferenceResult` / `StepResult`.

Treat anomaly handling as a distributed path: the simulator or provider can emit anomalies, the safety layer can convert them into warnings or stops, and the repository/logging layer can preserve the outcome for later analysis.

Prefer the smallest viable runtime first: start with mock hardware, lightweight repository behavior, and smaller local-model backends, then scale up to richer persistence, larger models, or hardware-in-the-loop once the contracts are stable.

For sensor-heavy systems, keep the profile as the source of truth: declare observation fields, camera roles, and safety thresholds there first, then let transports and adapters translate device-specific data into the normalized runtime contract.