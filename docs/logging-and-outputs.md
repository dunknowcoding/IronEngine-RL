# Logging and Outputs

Runtime summaries and generated outputs should be organized under `logs/` so example runs, framework runs, and custom hardware runs do not get mixed together.

## Recommended Structure

- `logs/framework/` - framework experiments and internal validation runs
- `logs/examples/` - runs from the canonical example profiles
- `logs/custom/` - user-defined robot integrations and experiments

## What To Store

- runtime summaries
- evaluation results
- compatibility snapshots
- task metrics
- repository notes and update instructions
- optional transport or telemetry traces when debugging hardware bring-up

## Default Repository Outputs

The built-in `KnowledgeRepository` writes lightweight run artifacts such as:

- `transitions.jsonl` - transition records per step
- `updates.jsonl` - repository updates and notes
- `summary.json` - final summary, manifests, compatibility, and evaluation

## Persistent Repository Example

The example repository plugin in `user_modules/examples/repositories/persistent_json_repository.py` also writes `repository_database.json`, which collects transitions, updates, and summary metadata in one JSON file for easier inspection or export.

## Recommended Practice

Use separate run directories for mock validation, HIL tests, and real hardware sessions so it is easy to compare safety behavior, transport health, task performance, and action-scheme changes over time.