# Roadmap

This page expands the high-level TODO list from `README.md` into a more structured roadmap for `IronEngine-RL`.

The guiding principle is simple: future work should stay task-oriented, testable, and easy to inspect through runnable profiles, deterministic scripts, and clear output artifacts.

## Task-Oriented Designs

### Near-term

- add reusable task blueprints for grasping, stacking, sorting, docking, inspection, and recovery
- add clearer task schemas that separate `goal`, `success_criteria`, `constraints`, `phase_gates`, and `failure_recovery`
- expand `SOUL.md` and `llm.task` examples for multi-stage and multi-object missions
- add stronger side-by-side examples comparing LLM-guided planning with custom PyTorch control on the same task

### Mid-term

- add task libraries for ARMSmart, mobile manipulators, and sensor-rich robots
- add user-facing templates for pick-place, inspection, exploration, and human-supervised workflows
- add shared mission packs that can be reused across simulation, mock hardware, and HIL profiles

## Unit Tests and Validation

### Near-term

- add more complete-profile regression tests for custom-model, anomaly-routing, and repository-backed workflows
- add deterministic tests for task-phase transitions such as `approach`, `pregrasp`, `grasp`, `lift`, and `place`
- add stronger validation coverage for path resolution, optional weights files, and custom-plugin contract mismatches

### Mid-term

- add scenario-based regression suites that replay fixed observations and confirm stable outputs
- add longer-horizon repository checks for `state_trace`, `reward_trace`, `policy_trace`, and update-log consistency
- add validation helpers that explain profile incompatibilities in more user-facing language

## Optimization

### Near-term

- optimize local-model loops for shorter prompts, lower latency, and better fallback quality on modest hardware
- improve custom PyTorch examples so adaptive updates are easier to inspect and compare across runs
- add lightweight profiling helpers for inference latency, transport timing, and repository overhead

### Mid-term

- add reusable run presets for benchmarking different providers or update strategies
- add selective caching and batching patterns that improve repeatability without obscuring control decisions
- reduce setup friction further through clearer environment diagnostics and reusable example launchers

## Visualization Tools

### Near-term

- add a lightweight run visualizer for `summary.json`, `transitions.jsonl`, and repository database files
- add policy-phase timelines for `approach`, `pregrasp`, `grasp`, `grasp_or_lift`, and safety overrides
- add reward-component plots for progress, alignment, visibility, safety, and success

### Mid-term

- add camera and detection overlays for replay debugging and target-selection analysis
- add multi-run comparison views for model variants and update-strategy changes
- add optional browser-based dashboards for trace inspection and run comparison

## Simulation Tools

### Near-term

- add richer simulation presets for clutter, distractors, occlusion, and recovery scenarios
- add deterministic simulation harnesses for documentation-grade verification
- add replay-assisted debugging that combines observations, camera frames, and repository state

### Mid-term

- add fault-injection presets for communication drops, battery degradation, sensor drift, and camera failures
- add curriculum-style simulation progressions from simple tabletop grasping to multi-stage manipulation
- add simulation bundles that mirror the same task across LLM, PyTorch, and heuristic controllers

## Future Improvements

- add a first-class experiment runner for sweeps, ablations, and benchmark summaries
- add stronger developer tooling for custom modules, including template generators and contract-aware scaffolds
- add better migration guidance from mock validation to HIL and real hardware
- add more polished example bundles with setup, deterministic runners, expected outputs, and troubleshooting in one place

## Success Standard

Each roadmap item should eventually lead to at least one of these:

- a runnable profile
- a deterministic validation script
- a regression test
- an inspectable output artifact
- or a user-facing document that reduces setup or debugging friction