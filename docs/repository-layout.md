# Repository Layout

## Top-Level Folders

- `src/ironengine_rl/` - framework implementation
- `profiles/` - reusable reference profiles for scaffolding, validation, tests, and canonical starting points
- `examples/` - runnable hardware, inference, and plugin examples
- `user_modules/` - user-defined and example plugins
- `tests/` - framework and smoke tests
- `assets/` - figure and reference files
- `docs/` - supporting documentation

## How to Think About `profiles/` vs `examples/`

Use `profiles/` for stable reference configurations that explain the framework shape itself. These are the best starting points for validation, scaffolding, understanding contracts, and creating your own derived profiles.

Use `examples/` for richer, scenario-driven demonstrations. Those profiles show how multiple pieces work together in practice, such as ARMSmart mock or HIL bring-up, local/cloud LLM providers, custom PyTorch providers, repository plugins, and complete end-to-end customization stacks.

A good workflow is:

1. inspect or validate a baseline in `profiles/`
2. run a matching scenario from `examples/`
3. copy the closer starting point into your own profile and customize it further

## Notable Example Areas

- `examples/hardware/` - hardware bring-up and grouped-hardware templates
- `examples/inference/` - LLM and custom PyTorch inference examples
- `examples/plugins/` - repository or other plugin-focused example profiles
- `user_modules/examples/repositories/` - opt-in persistent repository example plugin

## About `tools/`

The `tools/` folder is optional. It can hold helper scripts such as migration tools, data converters, release helpers, or local automation, but runtime modules do not need to live there.

This repository does not currently include a `tools/` folder because no dedicated utility scripts are required right now. If future maintenance or release workflows need helper scripts, the folder can be added back without affecting the framework runtime.

## Related Pages

- `docs/examples-and-workflows.md` for runnable starting paths
- `docs/customization.md` for profile and plugin customization patterns
- `README.md` for the top-level project overview