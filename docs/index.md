# Documentation Index

This folder contains the supporting documentation for `IronEngine-RL`. The root `README.md` gives the project overview, while the files here provide more detailed guidance for setup, architecture, examples, extensions, and hardware integration.

## Documents

- `software-setup.md` - Python environment setup, dependency roles, external tools, scaffold usage, and bring-up notes
- `troubleshooting.md` - common setup, validation, plugin, LLM, and hardware bring-up issues with quick recovery steps
- `profiles-and-configuration.md` - profile structure, key sections, and the recommended editing workflow
- `llm-task-and-soul.md` - how `SOUL.md` and `llm.task` guide LLM-backed inference inside the framework
- `anomaly-detection-and-safety.md` - how anomaly signals flow through inference, safety, and customization patterns
- `examples-matrix.md` - feature comparison across the main example profiles
- `api-reference.md` - public runtime APIs, datamodels, ports, CLI entry points, and plugin-loading shape
- `developer-guide.md` - detailed developer workflow guidance for extending, testing, and maintaining the project
- `framework-architecture.md` - architecture, manifests, aliases, action-scheme surfaces, and framework design goals
- `figure-7-1-mapping.md` - mapping from the Figure 7.1 concepts to concrete modules, aliases, examples, and plugin paths
- `customization.md` - customization patterns for modules, contracts, ARMSmart, action schemes, repositories, and scaffolding
- `custom-robots-and-sensors.md` - practical requirements for integrating custom robots, sensors, MCUs, interfaces, and action-scheme design
- `examples-and-workflows.md` - example catalog and recommended onboarding workflow
- `plugins-and-extensions.md` - plugin structure and extension points, including repository plugins
- `logging-and-outputs.md` - how runtime outputs, summaries, repository files, and logs should be organized
- `repository-layout.md` - top-level folder purpose, including the optional `tools/` folder
- `references.md` - dissertation citation, figure reference, and link to the Figure 7.1 mapping page

## Repository Legal Files

- `../LICENSE` - full `PolyForm Noncommercial License 1.0.0` text for this repository
- `../NOTICE` - required redistribution notice line for `DunknowCoding`
- `../SOUL.md` - the default LLM role contract used by prompt-driven and LLM-style providers

## Recommended Task-Setup Reading Path

If your goal is to let a user set a concrete LLM mission such as grasping the correct object or folding a cloth, read these in order:

1. `../SOUL.md`
2. `profiles-and-configuration.md`
3. `llm-task-and-soul.md`
4. `customization.md`
5. `api-reference.md`

### Fast answer: where to set the task

- set the user mission in `llm.task`
- keep the role contract in `llm.role_contract_file`
- keep evaluation wiring in `evaluation.task`
- keep control expectations in `action_scheme`
- use `model_provider.task` only for provider-specific overrides