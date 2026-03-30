from __future__ import annotations

from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo_root / 'src'))
sys.path.insert(0, str(repo_root))

from ironengine_rl.config import load_profile
from ironengine_rl.interfaces import CameraFrame, Observation
from ironengine_rl.inference import provider_from_profile


def main() -> None:
    profile = load_profile(Path(__file__).resolve().parent / 'profile.json')
    provider = provider_from_profile(profile)
    observation = Observation(
        timestamp_s=0.1,
        sensors={
            'object_dx': 0.24,
            'object_dy': 0.02,
            'claw_alignment': 0.84,
            'arm_extension': 0.52,
            'arm_height': 0.26,
            'battery_level': 0.93,
            'collision_risk': 0.04,
        },
        cameras=[
            CameraFrame(camera_id='dash_cam_hw', role='dash', timestamp_s=0.1, features={'target_visibility': 0.88}),
            CameraFrame(camera_id='claw_cam_hw', role='claw', timestamp_s=0.1, features={'target_visibility': 0.67}),
        ],
    )
    result = provider.infer(observation, {'repository_notes': ['demo'], 'success_rate': 0.5})
    print(result)


if __name__ == '__main__':
    main()
