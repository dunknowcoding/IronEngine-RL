from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl.config import load_profile
from ironengine_rl.evaluations import evaluation_suite_from_profile  # noqa: F401
from ironengine_rl.interfaces import ActionCommand, CameraFrame, InferenceResult, Observation, RewardBreakdown, StepResult
from ironengine_rl.training.update_strategies import RepositoryLinearBlendUpdate
from user_modules.examples.agents.armsmart_action_scheme_agent import ARMSmartActionSchemeAgent
from user_modules.examples.metrics.sensor_health_metric import SensorHealthMetric
from user_modules.examples.repositories.armsmart_experiment_repository import ARMSmartExperimentRepository
from user_modules.examples.repositories.persistent_json_repository import PersistentJsonRepository
from user_modules.examples.safety.multi_sensor_guard_policy import MultiSensorGuardSafetyPolicy
from user_modules.examples.inference.armsmart_adaptive_torch_provider import ARMSmartAdaptiveTorchProvider
from user_modules.examples.update.armsmart_reward_blend_update import ARMSmartRewardBlendUpdate


def _make_observation(**sensor_overrides: float) -> Observation:
    sensors = {
        "connection_alive": 1.0,
        "battery_level": 0.9,
        "collision_risk": 0.05,
        "object_dx": 0.2,
        "object_dy": 0.0,
        "claw_alignment": 0.8,
        "arm_extension": 0.3,
        "arm_height": 0.2,
        "gripper_close": 0.1,
        "object_grasped": 0.0,
    }
    sensors.update(sensor_overrides)
    return Observation(
        timestamp_s=0.1,
        sensors=sensors,
        cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.85})],
    )


class UpdateStrategyBehaviorTest(unittest.TestCase):
    def test_repository_linear_blend_update_adjusts_expected_weights(self) -> None:
        strategy = RepositoryLinearBlendUpdate(blend_factor=0.12, success_gain=0.08)
        weights = {"pregrasp_ready": 0.3, "visibility": 0.1, "object_distance": 0.5}
        adjusted = strategy.apply(weights, {"claw_alignment": 0.5}, {"success_rate": 0.25})

        self.assertEqual(weights["pregrasp_ready"], 0.3)
        self.assertAlmostEqual(adjusted["pregrasp_ready"], 0.39)
        self.assertAlmostEqual(adjusted["visibility"], 0.16)
        self.assertAlmostEqual(adjusted["object_distance"], 0.48)

    def test_armsmart_reward_blend_update_uses_reward_and_state_context(self) -> None:
        strategy = ARMSmartRewardBlendUpdate()
        weights = {
            "claw_alignment": 0.2,
            "visibility": 0.1,
            "pregrasp_ready": 0.3,
            "object_distance": 0.5,
            "collision_risk": 0.4,
            "battery_level": 0.0,
        }
        adjusted = strategy.apply(
            weights,
            {
                "claw_alignment": 0.5,
                "visibility": 0.8,
                "distance_progress": 0.2,
                "collision_risk": 0.3,
                "grasp_confidence": 0.4,
            },
            {
                "recent_reward_summary": {"progress": 0.6, "safety": 0.2},
                "state_summary": {"grasp_confidence": 0.7},
                "success_rate": 0.8,
                "battery_margin": 0.5,
            },
        )

        self.assertAlmostEqual(adjusted["claw_alignment"], 0.24)
        self.assertAlmostEqual(adjusted["visibility"], 0.132)
        self.assertAlmostEqual(adjusted["pregrasp_ready"], 0.37)
        self.assertAlmostEqual(adjusted["object_distance"], 0.416)
        self.assertAlmostEqual(adjusted["collision_risk"], 0.364)
        self.assertAlmostEqual(adjusted["battery_level"], 0.02)

    def test_armsmart_provider_reports_adaptive_weight_updates(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_pytorch_complete" / "profile.json")
        provider = ARMSmartAdaptiveTorchProvider(profile=profile, config=profile["model_provider"])
        observation = Observation(
            timestamp_s=0.1,
            sensors={
                "connection_alive": 1.0,
                "battery_level": 0.91,
                "collision_risk": 0.08,
                "object_dx": 0.24,
                "object_dy": 0.02,
                "claw_alignment": 0.76,
                "arm_extension": 0.42,
                "arm_height": 0.24,
                "gripper_close": 0.12,
            },
            cameras=[
                CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.82}),
                CameraFrame(camera_id="claw", role="claw", timestamp_s=0.1, features={"target_visibility": 0.74}),
            ],
        )

        base_result = provider.infer(observation, {"database": {"enabled": True}})
        adapted_result = provider.infer(
            observation,
            {
                "database": {"enabled": True},
                "recent_reward_summary": {"progress": 0.9, "safety": 0.05},
                "state_summary": {"grasp_confidence": 0.88},
                "success_rate": 0.85,
                "battery_margin": 0.5,
            },
        )

        self.assertIn("adaptive_pregrasp_weight", adapted_result.state_estimate)
        self.assertGreater(
            adapted_result.state_estimate["adaptive_pregrasp_weight"],
            base_result.state_estimate["adaptive_pregrasp_weight"],
        )
        self.assertLess(
            adapted_result.state_estimate["adaptive_distance_weight"],
            base_result.state_estimate["adaptive_distance_weight"],
        )
        self.assertTrue(any(note.startswith("Weights path:") for note in adapted_result.notes))
        if provider.torch_available:
            self.assertNotEqual(adapted_result.state_estimate["policy_score"], base_result.state_estimate["policy_score"])


class ARMSmartActionSchemeAgentBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ARMSmartActionSchemeAgent(profile={})
        self.context = {
            "action_scheme": {
                "name": "armsmart_pick_place_schedule",
                "schedule_notes": ["approach before arm extension"],
            }
        }

    def test_collision_risk_forces_hold_phase(self) -> None:
        action = self.agent.act(
            _make_observation(collision_risk=0.81),
            InferenceResult(task_phase="approach", state_estimate={"object_distance": 0.6}, reward_hints={}),
            self.context,
        )
        self.assertEqual(action.action_scheme, "armsmart_pick_place_schedule")
        self.assertEqual(action.auxiliary["policy_phase"], "hold")
        self.assertEqual(action.chassis_forward, 0.0)

    def test_approach_phase_generates_chassis_motion(self) -> None:
        action = self.agent.act(
            _make_observation(),
            InferenceResult(task_phase="approach", state_estimate={"object_distance": 0.5, "heading_error_deg": 9.0, "grasp_confidence": 0.2}, reward_hints={}),
            self.context,
        )
        self.assertEqual(action.auxiliary["policy_phase"], "approach")
        self.assertAlmostEqual(action.chassis_forward, 0.16)
        self.assertAlmostEqual(action.chassis_turn, -0.2)
        self.assertAlmostEqual(action.arm_lift, 0.08)
        self.assertEqual(action.auxiliary["schedule_notes_used"], 1.0)

    def test_pregrasp_phase_extends_arm_and_turns_wrist(self) -> None:
        action = self.agent.act(
            _make_observation(arm_extension=0.4),
            InferenceResult(task_phase="pregrasp", state_estimate={"object_distance": 0.2, "heading_error_deg": 12.0, "grasp_confidence": 0.3}, reward_hints={}),
            self.context,
        )
        self.assertEqual(action.auxiliary["policy_phase"], "pregrasp")
        self.assertAlmostEqual(action.arm_extend, 0.1)
        self.assertAlmostEqual(action.wrist_yaw, -0.15)
        self.assertAlmostEqual(action.arm_lift, 0.05)

    def test_grasp_phase_closes_gripper_and_lifts_when_object_is_grasped(self) -> None:
        action = self.agent.act(
            _make_observation(arm_extension=0.5, gripper_close=0.1, object_grasped=1.0),
            InferenceResult(task_phase="grasp", state_estimate={"object_distance": 0.15, "heading_error_deg": 0.0, "grasp_confidence": 0.8}, reward_hints={}),
            self.context,
        )
        self.assertEqual(action.auxiliary["policy_phase"], "grasp_or_lift")
        self.assertAlmostEqual(action.gripper_close, 0.7)
        self.assertAlmostEqual(action.arm_lift, 0.12)
        self.assertEqual(action.action_scheme, "armsmart_pick_place_schedule")


class PersistentRepositoryBehaviorTest(unittest.TestCase):
    def test_persistent_json_repository_writes_database_and_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "plugins" / "persistent_repository" / "profile.json")

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = PersistentJsonRepository(profile=profile, run_dir=Path(temp_dir), config=profile["repository"])
            observation = _make_observation()
            inference = InferenceResult(task_phase="grasp", state_estimate={"object_distance": 0.14}, reward_hints={"progress": 1.0})
            action = ActionCommand(chassis_forward=0.1, gripper_close=0.8)
            action.action_scheme = profile["action_scheme"]["name"]
            step_result = StepResult(
                observation=observation,
                reward=RewardBreakdown(total=2.0, components={"progress": 1.4, "alignment": 0.6}),
                done=True,
                info={"success": True},
            )

            repository.record_transition(observation, inference, action, step_result)
            repository.apply_update_instructions({"note": "promote stable grasp policy", "action_graph": {"grasp": ["lift"]}})
            summary_path = repository.write_summary()
            database_path = Path(temp_dir) / "repository_database.json"
            payload = json.loads(database_path.read_text(encoding="utf-8"))

            self.assertTrue(summary_path.exists())
            self.assertTrue(database_path.exists())
            self.assertEqual(payload["metadata"]["repository_type"], "persistent_json_repository")
            self.assertEqual(payload["metadata"]["transition_count"], 1)
            self.assertEqual(payload["metadata"]["update_count"], 1)
            self.assertEqual(payload["metadata"]["summary_path"], str(summary_path))
            self.assertEqual(payload["transitions"][0]["command"]["action_scheme"], profile["action_scheme"]["name"])
            self.assertEqual(payload["summary"]["success_rate"], 1.0)

    def test_armsmart_experiment_repository_tracks_state_reward_and_policy_traces(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_pytorch_complete" / "profile.json")

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ARMSmartExperimentRepository(profile=profile, run_dir=Path(temp_dir), config=profile["repository"])
            observation = _make_observation(battery_level=0.25, arm_extension=0.42)
            inference = InferenceResult(
                task_phase="pregrasp",
                state_estimate={"grasp_confidence": 0.66, "object_distance": 0.21},
                reward_hints={"progress": 1.0},
            )
            action = ActionCommand(arm_extend=0.1, gripper_close=0.4)
            action.action_scheme = profile["action_scheme"]["name"]
            action.auxiliary["policy_phase"] = "pregrasp"
            step_result = StepResult(
                observation=observation,
                reward=RewardBreakdown(total=1.9, components={"progress": 1.2, "alignment": 0.6, "safety": 0.1}),
                done=False,
                info={"success": False},
            )

            repository.record_transition(observation, inference, action, step_result)
            context = repository.build_context()
            repository.write_summary()
            database_path = Path(temp_dir) / "armsmart_experiment_db.json"
            payload = json.loads(database_path.read_text(encoding="utf-8"))

            self.assertAlmostEqual(context["recent_reward_summary"]["progress"], 1.2)
            self.assertAlmostEqual(context["state_summary"]["grasp_confidence"], 0.66)
            self.assertAlmostEqual(context["battery_margin"], 0.10)
            self.assertEqual(len(payload["state_trace"]), 1)
            self.assertEqual(len(payload["reward_trace"]), 1)
            self.assertEqual(len(payload["policy_trace"]), 1)
            self.assertEqual(payload["policy_trace"][0]["phase"], "pregrasp")
            self.assertEqual(payload["policy_trace"][0]["action_scheme"], profile["action_scheme"]["name"])


class SensorGuardBehaviorTest(unittest.TestCase):
    def test_sensor_health_metric_counts_alert_conditions(self) -> None:
        metric = SensorHealthMetric(config={"front_range_alert_threshold_m": 0.25, "air_quality_alert_threshold": 150.0, "stop_gesture_threshold": 0.5})
        step_result = StepResult(
            observation=_make_observation(front_range_m=0.18, air_quality_index=170.0, operator_stop_gesture=1.0),
            reward=RewardBreakdown(total=0.5, components={"safety": 0.5}),
            done=False,
            info={},
        )
        metric.update(ActionCommand(), step_result)
        summary = metric.summary(episodes=1, successes=0, reward_total=0.5)

        self.assertEqual(summary["front_range_alerts"], 1)
        self.assertEqual(summary["air_quality_alerts"], 1)
        self.assertEqual(summary["stop_gesture_events"], 1)

    def test_multi_sensor_guard_policy_stops_on_stop_gesture(self) -> None:
        policy = MultiSensorGuardSafetyPolicy(profile={"safety": {}}, config={"stop_gesture_threshold": 0.5, "gesture_confidence_threshold": 0.7})
        observation = _make_observation(operator_stop_gesture=1.0, gesture_confidence=0.95)
        action = ActionCommand(chassis_forward=0.2, arm_extend=0.1)
        safe_action = policy.apply(action, observation, InferenceResult(task_phase="approach", state_estimate={}, reward_hints={}))

        self.assertEqual(safe_action.chassis_forward, 0.0)
        self.assertEqual(safe_action.arm_extend, 0.0)
        self.assertEqual(safe_action.auxiliary["safety_reason_gesture_stop"], 1.0)

    def test_multi_sensor_guard_policy_warns_on_environmental_risk(self) -> None:
        policy = MultiSensorGuardSafetyPolicy(profile={"safety": {}}, config={"air_quality_warn_threshold": 150.0, "motor_temp_warn_threshold_c": 65.0})
        observation = _make_observation(air_quality_index=180.0, motor_temp_c=72.0)
        action = ActionCommand(arm_lift=0.2, arm_extend=0.3)
        safe_action = policy.apply(action, observation, InferenceResult(task_phase="approach", state_estimate={}, reward_hints={}))

        self.assertEqual(safe_action.auxiliary["air_quality_warning"], 1.0)
        self.assertEqual(safe_action.auxiliary["motor_temp_warning"], 1.0)
        self.assertEqual(safe_action.arm_lift, 0.0)
        self.assertEqual(safe_action.arm_extend, 0.0)


if __name__ == "__main__":
    unittest.main()