from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    import torch
except Exception as exc:  # pragma: no cover - convenience script
    raise SystemExit(f"Torch is required to generate demo weights: {exc}")

from user_modules.examples.inference.armsmart_adaptive_torch_provider import ARMSmartPolicyNet


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "weights"
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(7)
    model = ARMSmartPolicyNet()
    output_path = output_dir / "demo_policy.pt"
    torch.save(model.state_dict(), output_path)
    print(output_path)


if __name__ == "__main__":
    main()
