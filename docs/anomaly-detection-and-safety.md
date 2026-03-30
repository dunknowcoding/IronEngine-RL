{
    "cells": [
        {
            "cell_type": "markdown",
            "id": "#VSC-a3f03ea0",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "# Anomaly Detection and Safety",
                "",
                "`IronEngine-RL` keeps anomaly detection and safety separate on purpose. Inference can surface anomaly labels or uncertainty, but the safety layer remains the final boundary before commands reach simulation or hardware.",
                "",
                "This page explains where anomaly signals come from, how they move through the runtime, and how to customize the response without turning the model into the safety controller."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-3d383f0d",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Core Flow",
                "",
                "1. observations and cameras provide the current robot state",
                "2. the inference provider emits task phase, state estimate, reward hints, and optional anomaly labels",
                "3. the agent proposes an `ActionCommand`",
                "4. the safety policy clamps, replaces, or stops the command when anomaly or boundary conditions require it",
                "5. runtime outputs record both the proposed and effective behavior for inspection",
                "",
                "This separation is important: anomaly detection helps the framework reason about risk, but safety logic still decides whether motion is allowed."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-e4d759a2",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Where Anomalies Come From",
                "",
                "Common anomaly sources in this repository include:",
                "",
                "- custom inference providers such as `user_modules/examples/inference/anomaly_aware_inference_provider.py`",
                "- sensor-health or camera-health checks performed during inference or safety evaluation",
                "- transport or observation freshness problems such as stale telemetry or missing frames",
                "- task-specific risk markers such as unexpected object loss, unstable grasp state, or route interruption",
                "",
                "An anomaly label is usually lightweight text such as `camera_dropout`, `stale_observation`, or a custom domain-specific warning."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-d043250c",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Safety Response Patterns",
                "",
                "Typical safety responses are:",
                "",
                "- **warning-only:** keep running but record the anomaly clearly in notes and outputs",
                "- **clamp:** reduce command magnitude or block part of the action surface",
                "- **hold:** replace the action with a neutral command for one or more steps",
                "- **stop:** terminate or hard-stop execution when the anomaly is unsafe to ignore",
                "",
                "The built-in pattern is to prefer explicit boundaries. If a condition can damage hardware or create unsafe motion, treat it as a safety decision rather than a prompt-formatting problem."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-f410321d",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Files to Look At",
                "",
                "- `examples/plugins/anomaly_customization/profile.json` - end-to-end example profile for anomaly-aware customization",
                "- `user_modules/examples/inference/anomaly_aware_inference_provider.py` - provider emitting configurable anomaly labels",
                "- `user_modules/examples/safety/anomaly_routing_policy.py` - safety policy mapping anomaly labels to warning or stop behavior",
                "- `src/ironengine_rl/core/safety.py` - core safety boundary application flow",
                "- `src/ironengine_rl/framework/validation.py` - profile validation before strict execution",
                "",
                "These files are the fastest path if you want to understand or change anomaly handling without reading the entire codebase."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-ce358c72",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Recommended Workflow",
                "",
                "1. start from `examples/plugins/anomaly_customization/profile.json`",
                "2. validate the profile before runtime execution",
                "3. run the example in mock or simulation mode first",
                "4. inspect `summary.json` and `transitions.jsonl` in `logs/` to confirm the effective safety response",
                "5. only then move the same anomaly policy toward HIL or hardware-facing profiles",
                "",
                "This keeps anomaly customization observable and testable before it can affect real devices."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-f7645158",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Practical Rule",
                "",
                "Use inference to describe risk, use the agent to propose behavior, and use safety to decide whether motion is allowed. That design keeps anomaly-aware behavior extensible without weakening the framework boundary model."
            ]
        }
    ]
}
