# Contributing to IronEngine-RL

## Workflow

- start from the closest existing profile or example
- keep changes focused and avoid unnecessary public-surface renames
- prefer additive extensions such as plugins, action schemes, and new examples over breaking rewrites
- update matching docs in `docs/` when runtime behavior or profile shape changes

## Development Expectations

- run validation and the smallest relevant test scope before broader changes
- keep safety behavior explicit when changing agents, inference providers, hardware adapters, or action channels
- when adding LLM-backed behavior, document how `SOUL.md` and `llm.task` are expected to be used
- preserve the project style and keep examples copyable

## Pull Request Notes

- describe what changed and why
- mention any new profile fields, plugin paths, or runtime artifacts
- include the validation or test command you used when practical