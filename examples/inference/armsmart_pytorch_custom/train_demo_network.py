from __future__ import annotations

from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo_root / 'src'))
sys.path.insert(0, str(repo_root))

try:
    import torch
    import torch.nn as nn
except Exception as exc:
    raise SystemExit('This example requires torch. Install dependencies from requirements.txt.') from exc

from user_modules.examples.inference.custom_torch_inference_provider import FEATURE_NAMES, TinyGraspNet


def synthetic_label(batch: torch.Tensor) -> torch.Tensor:
    object_dx = batch[:, 0].abs()
    claw_alignment = batch[:, 2]
    arm_extension = batch[:, 3]
    battery_level = batch[:, 5]
    collision_risk = batch[:, 6]
    visibility = batch[:, 7]
    score = 0.9 * claw_alignment + 0.6 * arm_extension + 0.4 * visibility + 0.2 * battery_level - 1.2 * object_dx - 0.8 * collision_risk
    return (score > 0.35).long()


def main() -> None:
    torch.manual_seed(7)
    model = TinyGraspNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = nn.CrossEntropyLoss()
    features = torch.rand(512, len(FEATURE_NAMES))
    labels = synthetic_label(features)
    for _ in range(60):
        logits = model(features)
        loss = loss_fn(logits, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    weights_dir = Path(__file__).resolve().parent / 'weights'
    weights_dir.mkdir(parents=True, exist_ok=True)
    output_path = weights_dir / 'demo_policy.pt'
    torch.save(model.state_dict(), output_path)
    print(output_path)


if __name__ == '__main__':
    main()
