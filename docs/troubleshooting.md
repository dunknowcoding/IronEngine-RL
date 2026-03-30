{
    "cells": [
        {
            "cell_type": "markdown",
            "id": "#VSC-0ff9a5b5",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "# Troubleshooting",
                "",
                "This page collects the most common setup, validation, inference, and hardware bring-up problems in `IronEngine-RL`, along with the fastest low-risk recovery steps.",
                "",
                "When in doubt, return to the safest workflow: validate first, run mock or simulation second, and only then move toward HIL or real hardware."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-10e8e1e2",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## First Recovery Commands",
                "",
                "```powershell",
                "python -m ironengine_rl.validate --profile examples\\hardware\\armsmart\\profile.mock.json --strict",
                "python -m ironengine_rl.describe --profile profiles\\framework_customizable\\profile.json",
                "python -m unittest discover -s tests -p \"test_*.py\" -v",
                "```",
                "",
                "If these baseline commands do not work, fix the environment or profile shape before debugging higher-level runtime behavior."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-d9c9675b",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Common Problems",
                "",
                "| Problem | Typical cause | Fastest fix |",
                "| --- | --- | --- |",
                "| `ModuleNotFoundError` or import failure | wrong Python interpreter or missing editable install path | activate the intended environment and rerun from the repo root |",
                "| validation reports compatibility issues | profile sections do not agree on platform, provider, evaluation, or action scheme | start from a known example profile and change one section at a time |",
                "| local LLM calls fail | Ollama or compatible local server is not running, wrong base URL, or wrong model name | verify the server first, then verify the profile model and URL |",
                "| custom PyTorch example falls back unexpectedly | `torch` or weights file is missing | install `torch` and generate or point to valid weights |",
                "| hardware-facing profile does nothing | transport or protocol setup is incomplete | return to mock, inspect encoded command metadata, then re-check transport settings |",
                "| `.vscode` or logs appear in git status | ignore rules were missing earlier or files were already tracked | keep `.gitignore` current and remove tracked local-only files from the index if needed |"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-755aac72",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## LLM and Prompt Issues",
                "",
                "If an LLM-backed example behaves strangely, check these in order:",
                "",
                "1. `llm.role_contract_file` points to `SOUL.md` or another valid role-contract path",
                "2. the user mission is written in `llm.task` instead of being hidden only inside free-form prompt text",
                "3. the selected provider and model name match a running service",
                "4. the profile validates before runtime execution",
                "5. the generated notes or prompt preview in the run output reflect the expected task",
                "",
                "Use `docs/llm-task-and-soul.md` when the problem is task wording or role-contract setup rather than transport or hardware behavior."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-c5ba2c29",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## PyTorch and Custom-Model Issues",
                "",
                "For custom-model paths, verify:",
                "",
                "- `torch` is installed in the active environment",
                "- the weights path exists when you expect learned weights to be loaded",
                "- the fallback path is understood, so a run is not mistaken for a trained-policy result",
                "- the action scheme, task, and update strategy are the same when comparing runs",
                "",
                "A good verification path is:",
                "",
                "```powershell",
                "python examples\\inference\\armsmart_pytorch_complete\\generate_demo_weights.py",
                "python tools\\run_armsmart_pytorch_grasp_trial.py",
                "```"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-94076d68",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Hardware and Transport Issues",
                "",
                "When a hardware profile does not respond as expected:",
                "",
                "- confirm the profile transport backend is the one you intended to use",
                "- confirm serial port, baud rate, host, or protocol command IDs are correct",
                "- inspect mock or hardware metadata such as encoded command hex before changing the agent logic",
                "- verify the safety layer is not intentionally clamping or stopping the command",
                "- keep HIL and real hardware behind a working mock path whenever possible",
                "",
                "For ARMSmart-specific command flow, see the servo-control section in `README.md` and the adapter implementation in `src/ironengine_rl/hardware_adapters/armsmart.py`."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-e3d68278",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## What to Inspect in Outputs",
                "",
                "When something is wrong, inspect the newest run directory under `logs/` and check these first:",
                "",
                "- `summary.json` for a high-level run result",
                "- `transitions.jsonl` for step-by-step command and observation history",
                "- repository database or trace files for policy, reward, and state changes",
                "- provider notes for model loading, prompt setup, and anomaly warnings",
                "",
                "These files usually show whether the issue is configuration, inference, safety, or transport."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "#VSC-4c92df3a",
            "metadata": {
                "language": "markdown"
            },
            "source": [
                "## Escalation Path",
                "",
                "If a problem is still unclear, reduce the setup to the smallest reproducible case:",
                "",
                "1. switch to a baseline profile in `profiles/`",
                "2. validate it with `--strict`",
                "3. move to the nearest example in `examples/`",
                "4. compare outputs instead of changing multiple subsystems at once",
                "",
                "This approach is usually faster than debugging a full custom stack with hardware, custom inference, and new safety logic all at the same time."
            ]
        }
    ]
}
