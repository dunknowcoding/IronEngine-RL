# Security Policy

## Reporting

If you discover a security issue in `IronEngine-RL`, report it privately to the maintainer instead of opening a public issue with exploit details.

## Scope

Security-sensitive areas in this repository include:

- transport and protocol handling
- plugin loading paths
- profile-driven runtime execution
- local and cloud model integration
- repository persistence and generated logs

## Guidance for Users

- review plugin sources before loading them through `custom_plugin`
- do not place secrets directly in profiles; prefer environment variables for credentials
- keep hardware safety limits enabled even when testing LLM-driven or trainable inference
- validate profiles before strict runtime execution