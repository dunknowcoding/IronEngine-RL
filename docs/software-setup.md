# Software Setup

This page explains the recommended Python environment setup, dependency roles, external tools, and early bring-up commands for `IronEngine-RL`.

## Recommended Python Setup

### Option A: `venv` example

```powershell
python -m venv .venv\IronEngine-RL
.\.venv\IronEngine-RL\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Option B: Conda example

```powershell
conda create -n IronEngine-RL python=3.11 -y
conda activate IronEngine-RL
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Once the environment is active, run framework commands with `python -m ...` so the currently selected environment provides the interpreter and installed packages.

### First commands to try

```powershell
python -m ironengine_rl.validate --profile examples\hardware\armsmart\profile.mock.json --strict
python -m ironengine_rl.describe --profile profiles\framework_customizable\profile.json
python -m ironengine_rl.scaffold --output profiles\my_robot\profile.json --guided-goal custom_hardware --name my_robot --guided-backend udp --overwrite
```

The scaffold command now generates an `action_scheme` block automatically, so a new profile already includes explicit command-channel, feedback-field, result-field, and schedule-note guidance.
## Dependency Roles

- `requests` - HTTP access for local model servers and cloud APIs
- `torch` - custom PyTorch models and trainable providers
- `pyserial` - serial transport for MCUs or robot controllers
- `opencv-python` - camera capture during HIL or real hardware runs

Install additional device-specific SDKs only when your cameras, depth sensors, CAN adapters, or robot controllers require them.
## External Tools You May Need

- camera drivers for USB or onboard cameras
- serial or USB bridge drivers for MCU communication
- vendor SDKs for specialized sensors such as depth or force sensors
- Ollama or another local inference runtime when using prompt-driven local backends
- API credentials in environment variables when using hosted inference services
## Practical Bring-Up Notes for Custom Hardware

A custom robot integration usually needs both software and firmware agreement on the same runtime contract:

- telemetry field names must match the declared platform capabilities
- action channels must be accepted by the MCU or controller at a predictable rate
- disconnect and stale-observation behavior should fail safely
- mock telemetry should be added before real hardware testing
- validation should pass before moving from mock transport to HIL or real hardware

Use `examples/hardware/custom_robots/template.profile.json` as the safest starting point for a new platform.
## Setup Notes for Customized Models

Use the active Python environment for all model-related commands so `torch`, the local package, and the example scripts resolve against the same interpreter.

### Recommended custom-model bring-up

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install torch
python -m ironengine_rl.cli --profile examples\inference\armsmart_pytorch_complete\profile.json --validate-only --strict
python examples\inference\armsmart_pytorch_complete\generate_demo_weights.py
python tools\run_armsmart_pytorch_grasp_trial.py
```

### Notices

- install `torch` explicitly if your base environment does not already include it
- the complete PyTorch example can fall back without weights, but that path is best for framework wiring checks rather than learned-weight comparisons
- if a custom provider uses relative paths such as `weights_file`, run from the repository root unless the provider resolves paths for you
- use the deterministic grasp-trial script when you want repeatable documentation-grade verification instead of open-ended runtime behavior