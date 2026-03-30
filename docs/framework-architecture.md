# Framework Architecture

`IronEngine-RL` is the configurable brain layer that sits between AI reasoning modules and robot platforms. Its design goal is to keep each major subsystem swappable while preserving consistent runtime contracts and safety boundaries.

## Main Layers

1. observations and camera features
2. inference or state estimation
3. knowledge repository context and update strategy
4. agent action selection
5. safety and boundary enforcement
6. actuation transport and feedback
7. task evaluation and results

## Runtime Surfaces

- `framework_manifest` - active modules, aliases, action-scheme metadata, and interface contracts
- `platform_manifest` - hardware or simulation capability description
- `compatibility` - contract mismatch report before strict execution
- `validation` - schema plus compatibility checks used by CLI and runtime preflight
- `action_scheme` - explicit command-channel, feedback-field, result-field, and schedule-note description
- `knowledge_repository` - lightweight context storage for summaries, action graphs, notes, and compatibility views

## Additive Naming Layer

`IronEngine-RL` keeps the core runtime types and adds clearer user-facing aliases:

- `ActionCommand.command` - command-oriented view of the action payload
- `Observation.feedback` - feedback-oriented view of the sensor payload
- `InferenceResult.results` and `StepResult.results` - result-oriented summaries
- `knowledge_repository` and `database` entries in repository context - explicit naming for lightweight memory versus opt-in persistence

## Supported Model Styles

- prompt-driven providers such as local Ollama or cloud APIs
- trainable and custom PyTorch providers
- deterministic or heuristic baselines
- plugin-loaded custom providers

For prompt-driven providers, `model_provider.update_strategy` is retained only as reference metadata and reported as a warning when present; it is not applied to already-trained LLM backends.

## Safety Philosophy

Safety limits remain outside the model so chassis motion, arm extension, collision limits, stale observation stops, and low battery rules can be enforced even if inference is wrong or incomplete.

## Related Pages

- `docs/figure-7-1-mapping.md` for the concept-to-code mapping
- `docs/customization.md` for practical configuration patterns
- `docs/examples-and-workflows.md` for starting points and generated profiles