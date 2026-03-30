# Examples Matrix

This page compares the main runnable examples in `IronEngine-RL` so users can quickly choose the nearest starting point for hardware bring-up, inference experiments, repository workflows, anomaly customization, or sensor-rich custom platforms.

| Example | Hardware path | Local LLM | Cloud LLM | PyTorch | Custom plugins | Persistent repository | Anomaly-focused | Multi-sensor focus | Best use |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `examples/hardware/armsmart/profile.mock.json` | Mock ARMSmart | No | No | No | No | No | No | No | safest first validation path for the ARMSmart reference platform |
| `examples/hardware/armsmart/profile.hil.json` | HIL ARMSmart | No | No | No | No | No | No | No | hardware-in-the-loop bring-up on the reference platform |
| `examples/hardware/custom_robots/template.profile.json` | Custom grouped hardware template | No | No | No | No | No | No | Template only | blank starting point for a new robot contract |
| `examples/hardware/custom_robots/udp_mobile_manipulator.profile.json` | Custom wheeled manipulator | No | No | No | Minimal | No | No | No | generic mobile manipulator transport and safety contract |
| `examples/hardware/custom_robots/visionless_link_monitor.profile.json` | Custom no-camera hardware | No | No | No | Yes | No | Indirect | No | telemetry-first or low-vision robot validation |
| `examples/hardware/custom_robots/multi_camera_sensor.profile.json` | Custom hardware with extra cameras | No | No | No | Minimal | No | No | Partial | camera-rich robot bring-up with additional sensing |
| `examples/hardware/custom_robots/multi_sensor_station.profile.json` | Custom grouped hardware | No | No | No | Minimal | No | Safety-ready | Yes | copyable sensor-rich robot profile with depth, LiDAR, IMU, ranging, environment, pressure, gesture, and audio-derived signals |
| `examples/hardware/custom_robots/multi_sensor_guarded.profile.json` | Custom grouped hardware | No | No | No | Yes | No | Safety-focused | Yes | sensor-rich mock-safe profile with custom guard-policy reactions and sensor-health evaluation |
| `examples/inference/armsmart_ollama/profile.json` | Mock ARMSmart | Yes | No | No | No | No | No | No | simplest local Ollama-backed reasoning path |
| `examples/inference/armsmart_ollama_complete/profile.json` | Mock ARMSmart | Yes | No | No | Yes | Yes | No | No | repository-aware complete local-model workflow |
| `examples/inference/armsmart_cloud_api/profile.json` | Mock ARMSmart | No | Yes | No | No | No | No | No | simplest cloud API reasoning path |
| `examples/inference/armsmart_cloud_complete/profile.json` | Mock ARMSmart | No | Yes | No | Yes | Yes | No | No | repository-aware complete cloud-model workflow |
| `examples/inference/armsmart_pytorch_custom/profile.json` | Mock ARMSmart | No | No | Yes | Yes | No | No | No | simple custom PyTorch provider integration |
| `examples/inference/armsmart_pytorch_complete/profile.json` | Mock ARMSmart | No | No | Yes | Yes | Yes | No | No | full custom PyTorch stack with update strategy, task, metric, agent, and repository |
| `examples/plugins/persistent_repository/profile.json` | Mock/simulation | No | No | No | Yes | Yes | No | No | lightweight runtime plus opt-in persistence and action-scheme metadata |
| `examples/plugins/anomaly_customization/profile.json` | Simulation | No | No | No | Yes | Optional | Yes | No | custom anomaly labeling and safety routing experimentation |

## Suggested Shortcuts

- Start with `examples/hardware/custom_robots/multi_sensor_station.profile.json` when you need a copyable multi-sensor contract instead of a blank template.
- Start with `examples/hardware/custom_robots/multi_sensor_guarded.profile.json` when you want the same grouped sensor contract plus safety-oriented behavior and sensor-health summaries.
- Start with `examples/hardware/custom_robots/template.profile.json` when you want the cleanest scaffold for a new robot family.
- Start with `examples/plugins/anomaly_customization/profile.json` when safety reactions and anomaly routing matter more than hardware variety.
- Start with `examples/inference/armsmart_pytorch_complete/profile.json` when you need the richest learning-oriented stack.
- Start with `examples/inference/armsmart_ollama_complete/profile.json` or `examples/inference/armsmart_cloud_complete/profile.json` when you want repository-aware local or cloud model orchestration.