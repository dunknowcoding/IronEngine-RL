from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ironengine_rl import describe as describe_module
from ironengine_rl import scaffold as scaffold_module
from ironengine_rl import validate as validate_module
from ironengine_rl.config import load_profile
from ironengine_rl.core import RuntimeOrchestrator
from ironengine_rl.evaluations import evaluation_suite_from_profile
from ironengine_rl.framework import build_active_platform_manifest, build_compatibility_report, build_framework_manifest, build_validation_report
from ironengine_rl.framework.factories import build_runtime_components
from ironengine_rl.inference import provider_from_profile
from ironengine_rl.interfaces import ActionCommand, CameraFrame, InferenceResult, Observation, RewardBreakdown, StepResult


class FrameworkCustomizationTest(unittest.TestCase):
    def test_framework_profile_normalizes_explicit_modules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "framework_customizable" / "profile.json")
        self.assertEqual(profile["model_provider"]["type"], "pytorch_trainable")
        self.assertEqual(profile["evaluation"]["task"], "tabletop_grasp")
        self.assertEqual(profile["model_provider"]["update_strategy"]["type"], "repository_linear_blend")

    def test_framework_manifest_exposes_boundaries_and_available_modules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "framework_customizable" / "profile.json")
        manifest = build_framework_manifest(profile)
        self.assertIn("boundary_conditions", manifest)
        self.assertIn("interface_requirements", manifest)
        self.assertEqual(manifest["active_modules"]["inference_engine"]["name"], "pytorch_trainable")
        self.assertIn("contract", manifest["active_modules"]["inference_engine"])
        self.assertIn("pytorch_trainable", manifest["available_modules"]["inference_engines"])
        self.assertIn("tabletop_grasp", manifest["available_modules"]["evaluations"]["tasks"])

    def test_framework_manifest_exposes_llm_task_context_for_prompt_profiles(self) -> None:
        profile = {
            "runtime": {"mode": "hardware"},
            "llm": {
                "role_contract_file": "SOUL.md",
                "task": {
                    "name": "right_object_grasp",
                    "goal": "Grasp the right object.",
                },
            },
            "model_provider": {"type": "ollama_prompt", "model": "llama3.1:8b"},
        }
        manifest = build_framework_manifest(profile)
        self.assertEqual(manifest["interface_requirements"]["llm_task"]["name"], "right_object_grasp")
        self.assertEqual(manifest["interface_requirements"]["llm_role_contract_file"], "SOUL.md")

    def test_platform_manifest_and_compatibility_report_are_generated(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "framework_customizable" / "profile.json")
        framework_manifest = build_framework_manifest(profile)
        platform_manifest = build_active_platform_manifest(profile)
        compatibility = build_compatibility_report(profile, framework_manifest, platform_manifest)
        self.assertIn("platform_type", platform_manifest)
        self.assertIn("compatible", compatibility)
        self.assertTrue(compatibility["compatible"])

    def test_generic_hardware_profile_is_compatible(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "custom_hardware_generic" / "profile.json")
        framework_manifest = build_framework_manifest(profile)
        platform_manifest = build_active_platform_manifest(profile)
        compatibility = build_compatibility_report(profile, framework_manifest, platform_manifest)
        self.assertEqual(platform_manifest["platform_type"], "custom_hardware")
        self.assertTrue(compatibility["compatible"])

    def test_additional_profile_examples_validate(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for profile_name in ["hardware_udp_generic", "visionless_generic", "multi_camera_custom_sensor", "armsmart_hil", "armsmart_mock"]:
            profile = load_profile(repo_root / "profiles" / profile_name / "profile.json")
            report = build_validation_report(profile)
            self.assertTrue(report["schema"]["valid"], profile_name)
            self.assertTrue(report["compatibility"]["compatible"], profile_name)

    def test_examples_folder_profiles_validate(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        example_profiles = [
            repo_root / "examples" / "hardware" / "armsmart" / "profile.mock.json",
            repo_root / "examples" / "hardware" / "armsmart" / "profile.hil.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "udp_mobile_manipulator.profile.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "visionless_link_monitor.profile.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "multi_camera_sensor.profile.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "multi_sensor_station.profile.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "multi_sensor_guarded.profile.json",
            repo_root / "examples" / "hardware" / "custom_robots" / "template.profile.json",
            repo_root / "examples" / "inference" / "armsmart_ollama" / "profile.json",
            repo_root / "examples" / "inference" / "armsmart_cloud_api" / "profile.json",
            repo_root / "examples" / "inference" / "armsmart_pytorch_custom" / "profile.json",
            repo_root / "examples" / "inference" / "armsmart_ollama_complete" / "profile.json",
            repo_root / "examples" / "inference" / "armsmart_cloud_complete" / "profile.json",
            repo_root / "examples" / "inference" / "armsmart_pytorch_complete" / "profile.json",
            repo_root / "examples" / "plugins" / "persistent_repository" / "profile.json",
        ]
        for profile_path in example_profiles:
            profile = load_profile(profile_path)
            report = build_validation_report(profile)
            self.assertTrue(report["schema"]["valid"], str(profile_path))
            self.assertTrue(report["compatibility"]["compatible"], str(profile_path))

    def test_manifest_exposes_additive_aliases_and_action_scheme(self) -> None:
        profile = {
            "runtime": {"mode": "simulation"},
            "action_scheme": {
                "name": "phased_grasp_schedule",
                "command_channels": ["arm_lift", "arm_extend", "gripper_close"],
                "feedback_fields": ["claw_alignment", "battery_level"],
                "result_fields": ["reward.total", "done"],
            },
        }
        manifest = build_framework_manifest(profile)
        requirements = manifest["interface_requirements"]
        self.assertEqual(requirements["action_scheme"]["name"], "phased_grasp_schedule")
        self.assertEqual(requirements["command_channels"], ["arm_lift", "arm_extend", "gripper_close"])
        self.assertEqual(requirements["feedback_fields"], ["claw_alignment", "battery_level"])
        self.assertEqual(requirements["naming_aliases"]["command"], "action_channels")

    def test_grouped_hardware_config_normalizes_armsmart_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "armsmart_mock" / "profile.json")
        self.assertEqual(profile["runtime"]["mode"], "hardware")
        self.assertEqual(profile["platform"]["type"], "armsmart_reference")
        self.assertEqual(profile["transport"]["backend"], "mock")
        self.assertEqual(profile["transport"]["serial_port"], "COM5")
        self.assertEqual(profile["transport"]["default_mode"], "arm")
        self.assertIn("protocol_commands", profile["transport"])
        self.assertEqual(profile["vision"]["dash_camera_id"], "dash_cam_hw")
        self.assertEqual(profile["vision"]["claw_camera_id"], "claw_cam_hw")
        self.assertEqual(profile["safety"]["collision_stop_threshold"], 0.8)

    def test_hardware_template_profile_validates(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "profiles" / "hardware_template" / "profile.json")
        report = build_validation_report(profile)
        self.assertTrue(report["schema"]["valid"])
        self.assertTrue(report["compatibility"]["compatible"])

    def test_multi_sensor_example_preserves_grouped_sensor_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "hardware" / "custom_robots" / "multi_sensor_station.profile.json")
        capabilities = profile["platform"]["capabilities"]
        self.assertIn("front_range_m", capabilities["observation_fields"])
        self.assertIn("depth_front", capabilities["camera_roles"])
        self.assertTrue(profile["hardware"]["sensors"]["lidar"]["enabled"])
        self.assertIn("imu_yaw_deg", profile["action_scheme"]["feedback_fields"])
        report = build_validation_report(profile)
        self.assertTrue(report["schema"]["valid"])
        self.assertTrue(report["compatibility"]["compatible"])

    def test_multi_sensor_guarded_example_includes_named_mock_scenarios(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "hardware" / "custom_robots" / "multi_sensor_guarded.profile.json")
        mock_cfg = profile["hardware"]["mock"]
        self.assertEqual(mock_cfg["active_scenario"], "guarded_nominal")
        self.assertIn("guarded_nominal", mock_cfg["scenarios"])
        self.assertIn("front_range_stop", mock_cfg["scenarios"])
        self.assertIn("gesture_stop", mock_cfg["scenarios"])
        self.assertIn("air_quality_warning", mock_cfg["scenarios"])
        self.assertGreaterEqual(len(mock_cfg["scenarios"]["guarded_nominal"]), 2)

    def test_scaffold_hardware_profile_generates_custom_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "my_robot" / "profile.json"
            profile = scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                example="template",
                name="my_robot",
                platform_type="my_robot_platform",
                backend="udp",
                overwrite=True,
            )
            self.assertTrue(output_path.exists())
            self.assertEqual(profile["hardware"]["platform"]["name"], "my_robot")
            self.assertEqual(profile["hardware"]["platform"]["type"], "my_robot_platform")
            self.assertEqual(profile["hardware"]["connection"]["backend"], "udp")
            self.assertIn("action_scheme", profile)
            self.assertEqual(profile["action_scheme"]["name"], "generated_action_scheme")
            self.assertIn("gripper_close", profile["action_scheme"]["command_channels"])
            normalized = load_profile(output_path)
            self.assertEqual(normalized["transport"]["backend"], "udp")
            self.assertEqual(normalized["logs"]["run_dir"], "logs/my_robot")

    def test_scaffold_preset_arm_only_reduces_camera_and_action_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "arm_only.json"
            scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                preset="arm_only",
                name="bench_arm",
                overwrite=True,
            )
            generated = load_profile(output_path)
            self.assertEqual(generated["platform"]["capabilities"]["camera_roles"], ["claw"])
            self.assertEqual(generated["vision"]["claw_camera_id"], "claw_cam_hw")
            self.assertNotIn("dash_camera_id", generated["vision"])
            self.assertEqual(generated["evaluation"]["task"]["contract"]["camera_roles"], ["claw"])
            self.assertEqual(generated["action_scheme"]["name"], "arm_only_action_scheme")
            self.assertEqual(generated["action_scheme"]["command_channels"], ["arm_lift", "arm_extend", "wrist_yaw", "gripper_close"])

    def test_scaffold_preset_visionless_uses_plugin_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "visionless.json"
            scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                preset="visionless_link_monitor",
                backend="udp",
                name="link_monitor",
                overwrite=True,
            )
            generated = load_profile(output_path)
            report = build_validation_report(generated)
            self.assertEqual(generated["platform"]["capabilities"]["camera_roles"], [])
            self.assertEqual(generated["model_provider"]["type"], "custom_plugin")
            self.assertEqual(generated["agent"]["type"], "custom_plugin")
            self.assertEqual(generated["boundary_conditions"]["type"], "custom_plugin")
            self.assertTrue(report["schema"]["valid"])
            self.assertTrue(report["compatibility"]["compatible"])

    def test_scaffold_cli_creates_armsmart_based_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated_armsmart.json"
            buffer = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [
                    "ironengine_rl.scaffold",
                    "--output",
                    str(output_path),
                    "--example",
                    "armsmart_mock",
                    "--name",
                    "demo_hw",
                    "--backend",
                    "mock",
                ]
                with redirect_stdout(buffer):
                    scaffold_module.main()
            finally:
                sys.argv = original_argv
            payload = json.loads(buffer.getvalue())
            generated = load_profile(output_path)
            self.assertEqual(payload["platform"]["name"], "demo_hw")
            self.assertEqual(generated["hardware"]["platform"]["name"], "demo_hw")
            self.assertEqual(generated["transport"]["backend"], "mock")
            self.assertEqual(payload["preset"], "default")
            self.assertIn("action_scheme", payload)
            self.assertIn("command_channels", payload["action_scheme"])

    def test_scaffold_guided_goal_selects_ollama_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "ollama_profile.json"
            generated = scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                guided_goal="local_ollama",
                name="armsmart_ollama_demo",
                overwrite=True,
            )
            normalized = load_profile(output_path)
            self.assertEqual(generated["scaffold_metadata"]["guided_goal"], "local_ollama")
            self.assertEqual(normalized["model_provider"]["type"], "ollama_prompt")
            self.assertEqual(normalized["transport"]["backend"], "mock")
            self.assertEqual(normalized["action_scheme"]["name"], "local_ollama_action_scheme")
            self.assertEqual(normalized["llm"]["role_contract_file"], "SOUL.md")
            self.assertIn("grasp the right object", normalized["llm"]["task"]["goal"].lower())

    def test_scaffold_guided_goal_selects_custom_pytorch_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "pytorch_profile.json"
            generated = scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                guided_goal="custom_pytorch",
                name="armsmart_torch_demo",
                overwrite=True,
            )
            normalized = load_profile(output_path)
            report = build_validation_report(normalized)
            self.assertEqual(generated["scaffold_metadata"]["guided_goal"], "custom_pytorch")
            self.assertEqual(normalized["model_provider"]["plugin"]["module_path"], "user_modules.examples.inference.custom_torch_inference_provider:CustomTorchPolicyProvider")
            self.assertEqual(normalized["action_scheme"]["name"], "custom_pytorch_action_scheme")
            self.assertTrue(report["schema"]["valid"])
            self.assertTrue(report["compatibility"]["compatible"])

    def test_scaffold_action_scheme_name_can_be_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "override_action_scheme.json"
            generated = scaffold_module.scaffold_hardware_profile(
                output_path=output_path,
                preset="visionless_link_monitor",
                action_scheme_name="telemetry_first_schedule",
                overwrite=True,
            )
            self.assertEqual(generated["action_scheme"]["name"], "telemetry_first_schedule")
            self.assertTrue(any("link-health" in note for note in generated["action_scheme"]["schedule_notes"]))

    def test_organized_plugin_modules_are_loadable(self) -> None:
        nested_paths = [
            "user_modules.examples.inference.custom_inference_provider:CustomInferenceProvider",
            "user_modules.examples.inference.visionless_inference_provider:VisionlessInferenceProvider",
            "user_modules.examples.inference.custom_torch_inference_provider:CustomTorchPolicyProvider",
            "user_modules.examples.inference.armsmart_adaptive_torch_provider:ARMSmartAdaptiveTorchProvider",
            "user_modules.examples.inference.armsmart_local_llm_provider:ARMSmartLocalLLMProvider",
            "user_modules.examples.inference.armsmart_cloud_llm_provider:ARMSmartCloudLLMProvider",
            "user_modules.examples.agents.stability_agent:StabilityAgent",
            "user_modules.examples.agents.armsmart_action_scheme_agent:ARMSmartActionSchemeAgent",
            "user_modules.examples.metrics.custom_visibility_metric:CustomVisibilityMetric",
            "user_modules.examples.metrics.sensor_health_metric:SensorHealthMetric",
            "user_modules.examples.repositories.armsmart_experiment_repository:ARMSmartExperimentRepository",
            "user_modules.examples.safety.connection_aware_policy:ConnectionAwareSafetyPolicy",
            "user_modules.examples.safety.multi_sensor_guard_policy:MultiSensorGuardSafetyPolicy",
        ]
        for module_path in nested_paths:
            symbol = module_path.split(":", maxsplit=1)[1]
            profile = {"model_provider": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            if symbol == "StabilityAgent":
                profile = {"agent": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            if symbol == "ARMSmartActionSchemeAgent":
                profile = {"agent": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            if symbol == "ARMSmartExperimentRepository":
                profile = {"repository": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            if symbol == "ConnectionAwareSafetyPolicy":
                profile = {"boundary_conditions": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            if symbol == "MultiSensorGuardSafetyPolicy":
                profile = {"boundary_conditions": {"type": "custom_plugin", "plugin": {"module_path": module_path}}}
            report = build_validation_report(profile)
            self.assertTrue(report["schema"]["valid"], module_path)

    def test_prompt_provider_style_is_loadable(self) -> None:
        profile = {
            "llm": {
                "role_contract_file": "SOUL.md",
                "task": {
                    "name": "right_object_grasp",
                    "goal": "Grasp the right object on the table.",
                    "success_criteria": ["choose the correct target"],
                },
            },
            "model_provider": {
                "type": "ollama_prompt",
                "model": "llama3.1:8b",
                "prompt_template": "grasp_controller_v1",
                "role_contract_file": "SOUL.md",
            }
        }
        provider = provider_from_profile(profile)
        observation = Observation(
            timestamp_s=0.1,
            sensors={"object_dx": 0.4, "object_dy": 0.1, "claw_alignment": 0.7, "battery_level": 0.9, "collision_risk": 0.0},
            cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.8})],
        )
        prompt = provider.build_prompt(observation, {"repository_notes": ["prefer stable approach"], "action_scheme": {"name": "precision_grasp"}})
        result = provider.infer(observation, {"repository_notes": [], "success_rate": 0.0})
        self.assertIn("SOUL contract", prompt)
        self.assertIn("Grasp the right object on the table.", prompt)
        self.assertTrue(any("Prompt-driven provider active" in note for note in result.notes))
        self.assertTrue(any("Resolved task: right_object_grasp" in note for note in result.notes))

    def test_validation_warns_when_custom_role_contract_is_missing(self) -> None:
        profile = {
            "llm": {"role_contract_file": "missing/SOUL.md", "task": "Fold a cloth."},
            "model_provider": {"type": "cloud_prompt", "model": "gpt-4.1-mini"},
        }
        report = build_validation_report(profile)
        self.assertTrue(report["schema"]["valid"])
        self.assertTrue(any(issue["code"] == "missing_role_contract_file" for issue in report["schema"]["issues"]))

    def test_prompt_provider_update_strategy_is_warn_only(self) -> None:
        profile = {
            "model_provider": {
                "type": "ollama_prompt",
                "model": "llama3.1:8b",
                "prompt_template": "grasp_controller_v1",
                "update_strategy": {"type": "repository_linear_blend"},
            }
        }
        report = build_validation_report(profile)
        self.assertTrue(report["schema"]["valid"])
        self.assertTrue(
            any(issue["code"] == "llm_update_strategy_ignored" and issue["severity"] == "warning" for issue in report["schema"]["issues"])
        )

    def test_custom_plugin_inference_provider_is_loadable(self) -> None:
        profile = {
            "model_provider": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.custom_inference_provider:CustomInferenceProvider"},
            }
        }
        provider = provider_from_profile(profile)
        observation = Observation(
            timestamp_s=0.1,
            sensors={"object_dx": 0.4, "object_distance": 0.3, "claw_alignment": 0.7, "arm_extension": 0.2, "arm_height": 0.1},
            cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.8})],
        )
        result = provider.infer(observation, {"repository_notes": [], "success_rate": 0.0})
        self.assertEqual(result.task_phase, "grasp")

    def test_custom_torch_plugin_provider_is_loadable_without_weights(self) -> None:
        profile = {
            "model_provider": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.inference.custom_torch_inference_provider:CustomTorchPolicyProvider"},
                "weights_file": "examples/inference/armsmart_pytorch_custom/weights/missing_demo_policy.pt",
                "grasp_threshold": 0.55,
            }
        }
        provider = provider_from_profile(profile)
        observation = Observation(
            timestamp_s=0.1,
            sensors={"object_dx": 0.2, "object_dy": 0.02, "claw_alignment": 0.8, "arm_extension": 0.45, "arm_height": 0.24, "battery_level": 0.9, "collision_risk": 0.02},
            cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.8})],
        )
        result = provider.infer(observation, {"repository_notes": [], "success_rate": 0.0})
        self.assertIn("Custom PyTorch inference provider active.", result.notes)
        self.assertIn(result.task_phase, {"approach", "grasp"})

    def test_custom_plugin_metric_is_loadable(self) -> None:
        profile = {
            "evaluation": {
                "task": "tabletop_grasp",
                "metrics": [
                    {"type": "custom_plugin", "plugin": {"module_path": "user_modules.examples.custom_metric:CustomVisibilityMetric"}}
                    ,
                    {"type": "custom_plugin", "plugin": {"module_path": "user_modules.examples.metrics.custom_visibility_metric:CustomVisibilityMetric"}},
                    {"type": "custom_plugin", "plugin": {"module_path": "user_modules.examples.metrics.sensor_health_metric:SensorHealthMetric"}}
                ],
            }
        }
        suite = evaluation_suite_from_profile(profile)
        observation = Observation(
            timestamp_s=0.1,
            sensors={"object_dx": 0.4, "object_dy": 0.1, "claw_alignment": 0.7, "battery_level": 0.9, "collision_risk": 0.0},
            cameras=[CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.8})],
        )
        step_result = StepResult(observation=observation, reward=RewardBreakdown(total=1.0, components={"progress": 1.0}), done=False, info={})
        suite.update(action=type("Action", (), {})(), step_result=step_result)
        summary = suite.summary(episodes=1, successes=0, reward_total=1.0)
        self.assertIn("custom_visibility", summary["metrics"])
        self.assertIn("sensor_health", summary["metrics"])

    def test_custom_agent_and_safety_plugins_are_loadable(self) -> None:
        profile = {
            "runtime": {"mode": "hardware"},
            "platform": {
                "name": "plugin_test_platform",
                "type": "custom_hardware",
                "capabilities": {
                    "transport_backends": ["udp"],
                    "observation_fields": ["connection_alive", "battery_level", "collision_risk", "arm_extension", "arm_height"],
                    "camera_roles": [],
                    "action_channels": [
                        "chassis_forward",
                        "chassis_strafe",
                        "chassis_turn",
                        "arm_lift",
                        "arm_extend",
                        "wrist_yaw",
                        "gripper_close"
                    ],
                },
            },
            "model_provider": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.inference.visionless_inference_provider:VisionlessInferenceProvider"},
                "contract": {"camera_roles": [], "observation_fields": ["connection_alive", "battery_level", "collision_risk", "arm_extension", "arm_height"]},
            },
            "agent": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.agents.stability_agent:StabilityAgent"},
            },
            "boundary_conditions": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.safety.connection_aware_policy:ConnectionAwareSafetyPolicy"},
                "contract": {"observation_fields": ["connection_alive", "battery_level", "collision_risk"]},
                "connection_hold_threshold": 0.6,
            },
        }
        components = build_runtime_components(profile)
        observation = Observation(
            timestamp_s=0.1,
            sensors={"connection_alive": 0.4, "battery_level": 0.9, "collision_risk": 0.1, "arm_extension": 0.1, "arm_height": 0.1},
            cameras=[],
        )
        inference = InferenceResult(task_phase="link_validation", state_estimate={}, reward_hints={"progress": 1.0})
        action = components.agent.act(observation, inference, {"success_rate": 0.0, "repository_notes": []})
        safe_action = components.safety.apply(action, observation, inference)
        self.assertIsInstance(action, ActionCommand)
        self.assertEqual(type(components.agent).__name__, "StabilityAgent")
        self.assertEqual(type(components.safety).__name__, "ConnectionAwareSafetyPolicy")
        self.assertEqual(safe_action.chassis_forward, 0.0)
        self.assertEqual(safe_action.auxiliary.get("connection_hold"), 1.0)

    def test_repository_custom_plugin_is_loadable(self) -> None:
        profile = {
            "runtime": {"mode": "simulation"},
            "simulator": {"max_steps": 4},
            "vision": {"backend": "replay", "dash_camera_id": "dash_cam", "claw_camera_id": "claw_cam", "replay_file": "profiles/replay_camera/vision_features.json"},
            "model_provider": {"type": "rule_based"},
            "repository": {
                "type": "custom_plugin",
                "plugin": {"module_path": "user_modules.examples.repositories.persistent_json_repository:PersistentJsonRepository"},
                "database_file": "repository_database.json",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            components = build_runtime_components(profile, run_dir=Path(temp_dir))
            self.assertEqual(type(components.repository).__name__, "PersistentJsonRepository")

    def test_complete_armsmart_pytorch_components_are_loadable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_pytorch_complete" / "profile.json")
        observation = Observation(
            timestamp_s=0.1,
            sensors={
                "connection_alive": 1.0,
                "battery_level": 0.91,
                "collision_risk": 0.04,
                "object_dx": 0.25,
                "object_dy": 0.02,
                "claw_alignment": 0.84,
                "arm_extension": 0.58,
                "arm_height": 0.29,
                "gripper_close": 0.22,
            },
            cameras=[
                CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.88}),
                CameraFrame(camera_id="claw", role="claw", timestamp_s=0.1, features={"target_visibility": 0.66}),
            ],
        )
        provider = provider_from_profile(profile)
        inference = provider.infer(
            observation,
            {
                "knowledge_repository": {"recent_events": ["approach stable"]},
                "database": {"enabled": True},
                "action_scheme": profile["action_scheme"],
                "recent_reward_summary": {"progress": 0.7, "safety": 0.1},
                "state_summary": {"grasp_confidence": 0.6},
                "success_rate": 0.8,
            },
        )
        self.assertIn("Adaptive ARMSmart PyTorch provider active.", inference.notes)
        self.assertIn(inference.task_phase, {"approach", "pregrasp", "grasp"})

        suite = evaluation_suite_from_profile(profile)
        step_result = StepResult(
            observation=observation,
            reward=RewardBreakdown(total=2.4, components={"progress": 1.2, "alignment": 0.7, "safety": 0.1}),
            done=False,
            info={"success": False},
        )
        suite.update(ActionCommand(), step_result)
        summary = suite.summary(episodes=1, successes=0, reward_total=2.4)
        self.assertIn("armsmart_reward_state", summary["metrics"])

        with tempfile.TemporaryDirectory() as temp_dir:
            components = build_runtime_components(profile, run_dir=Path(temp_dir))
            self.assertEqual(type(components.agent).__name__, "ARMSmartActionSchemeAgent")
            self.assertEqual(type(components.repository).__name__, "ARMSmartExperimentRepository")

    def test_complete_local_and_cloud_llm_providers_are_loadable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        observation = Observation(
            timestamp_s=0.1,
            sensors={
                "connection_alive": 1.0,
                "battery_level": 0.9,
                "collision_risk": 0.05,
                "object_dx": 0.42,
                "object_dy": 0.03,
                "claw_alignment": 0.73,
                "arm_extension": 0.36,
                "arm_height": 0.24,
            },
            cameras=[
                CameraFrame(camera_id="dash", role="dash", timestamp_s=0.1, features={"target_visibility": 0.82}),
                CameraFrame(camera_id="claw", role="claw", timestamp_s=0.1, features={"target_visibility": 0.54}),
            ],
        )
        context = {
            "knowledge_repository": {"recent_events": ["target reacquired"]},
            "database": {"enabled": True},
            "repository_notes": ["keep safety limits strict"],
            "action_scheme": {"name": "armsmart_prompt_schedule"},
            "recent_reward_summary": {"progress": 0.4},
            "state_summary": {"grasp_confidence": 0.45},
            "success_rate": 0.5,
        }

        local_profile = load_profile(repo_root / "examples" / "inference" / "armsmart_ollama_complete" / "profile.json")
        local_result = provider_from_profile(local_profile).infer(observation, context)
        self.assertIn("Local LLM ARMSmart provider active.", local_result.notes)

        cloud_profile = load_profile(repo_root / "examples" / "inference" / "armsmart_cloud_complete" / "profile.json")
        cloud_result = provider_from_profile(cloud_profile).infer(observation, context)
        self.assertIn("Cloud LLM ARMSmart provider active.", cloud_result.notes)

    def test_local_llm_provider_uses_live_ollama_decision_when_enabled(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_ollama_complete" / "profile.json")
        profile["model_provider"]["live_inference"] = True
        profile["model_provider"]["model"] = "qwen3.5:4b"
        observation = Observation(
            timestamp_s=0.2,
            sensors={
                "connection_alive": 1.0,
                "battery_level": 0.92,
                "collision_risk": 0.02,
                "object_dx": 0.18,
                "object_dy": 0.01,
                "object_distance": 0.18,
                "claw_alignment": 0.89,
                "pregrasp_ready": 1.0,
                "arm_extension": 0.58,
                "arm_height": 0.2,
                "gripper_close": 0.2,
            },
            cameras=[
                CameraFrame(camera_id="dash", role="dash", timestamp_s=0.2, features={"target_visibility": 0.9}, detections=[{"label": "red_mug", "confidence": 0.92, "is_target": True}]),
                CameraFrame(camera_id="claw", role="claw", timestamp_s=0.2, features={"target_visibility": 0.8}, detections=[{"label": "red_mug", "confidence": 0.88, "is_target": True}]),
            ],
            metadata={"target_object_label": "red_mug"},
        )
        fake_response = Mock()
        fake_response.read.return_value = json.dumps({
            "response": json.dumps(
                {
                    "task_phase": "grasp",
                    "grasp_confidence": 0.91,
                    "target_object": "red_mug",
                    "notes": ["target isolated"],
                }
            )
        }).encode("utf-8")
        fake_response.__enter__ = Mock(return_value=fake_response)
        fake_response.__exit__ = Mock(return_value=None)
        with patch("ironengine_rl.inference.ollama_client.urlopen", return_value=fake_response):
            result = provider_from_profile(profile).infer(observation, {"action_scheme": profile["action_scheme"], "repository_notes": []})
        self.assertEqual(result.task_phase, "grasp")
        self.assertAlmostEqual(result.state_estimate["grasp_confidence"], 0.91)
        self.assertTrue(any("Live Ollama decision used" in note for note in result.notes))
        self.assertTrue(any("LLM selected target: red_mug" in note for note in result.notes))

    def test_simulation_scene_objects_include_target_and_distractors(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_ollama_target_selection" / "profile.json")
        components = build_runtime_components(profile, run_dir=repo_root / "logs" / "test_scene_objects")
        observation = components.environment.reset()
        self.assertEqual(observation.metadata["target_object_label"], "red_mug")
        self.assertEqual(len(observation.metadata["scene_objects"]), 3)
        dash = next(camera for camera in observation.cameras if camera.role == "dash")
        self.assertEqual(len(dash.detections), 3)
        self.assertTrue(any(item.get("label") == "red_mug" and item.get("is_target") for item in dash.detections))

    def test_local_llm_provider_live_prompt_is_compact(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_ollama_target_selection" / "profile.json")
        provider = provider_from_profile(profile)
        components = build_runtime_components(profile, run_dir=repo_root / "logs" / "test_live_prompt_compact")
        observation = components.environment.reset()
        context = components.repository.build_context()
        verbose_prompt, metadata = provider._build_prompt(observation, context)
        fallback = provider._enrich_fallback(provider.fallback.infer(observation, context), observation)
        live_prompt = provider._build_live_prompt(observation, context, metadata, fallback)
        self.assertLess(len(live_prompt), len(verbose_prompt))
        self.assertIn("Visible objects", live_prompt)
        self.assertIn("Return JSON only", live_prompt)

    def test_local_llm_provider_reuses_cached_decision_for_same_signature(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_profile(repo_root / "examples" / "inference" / "armsmart_ollama_target_selection" / "profile.json")
        profile["model_provider"]["live_inference"] = True
        profile["model_provider"]["decision_cache_reuse_steps"] = 2
        provider = provider_from_profile(profile)
        components = build_runtime_components(profile, run_dir=repo_root / "logs" / "test_live_prompt_cache")
        observation = components.environment.reset()
        context = components.repository.build_context()
        fake_response = Mock()
        fake_response.read.return_value = json.dumps({
            "response": json.dumps({
                "task_phase": "approach",
                "grasp_confidence": 0.55,
                "target_object": "red_mug",
                "notes": ["stay on target"],
            })
        }).encode("utf-8")
        fake_response.__enter__ = Mock(return_value=fake_response)
        fake_response.__exit__ = Mock(return_value=None)
        with patch("ironengine_rl.inference.ollama_client.urlopen", return_value=fake_response) as mocked_urlopen:
            first = provider.infer(observation, context)
            second = provider.infer(observation, context)
        self.assertEqual(mocked_urlopen.call_count, 1)
        self.assertEqual(first.task_phase, second.task_phase)
        self.assertTrue(any("Live Ollama decision used" in note for note in second.notes))

    def test_additive_alias_properties_are_available(self) -> None:
        observation = Observation(timestamp_s=0.1, sensors={"battery_level": 0.9}, cameras=[])
        inference = InferenceResult(task_phase="approach", state_estimate={"distance": 0.2}, reward_hints={"progress": 1.0})
        action = ActionCommand(chassis_forward=0.4)
        action.action_scheme = "phased_grasp_schedule"
        step_result = StepResult(observation=observation, reward=RewardBreakdown(total=1.5, components={"progress": 1.5}), done=False, info={"success": False})
        self.assertEqual(observation.feedback["battery_level"], 0.9)
        self.assertEqual(inference.results["task_phase"], "approach")
        self.assertEqual(action.command["action_scheme"], "phased_grasp_schedule")
        self.assertEqual(step_result.results["reward_total"], 1.5)

    def test_validation_report_flags_invalid_plugin_specs(self) -> None:
        report = build_validation_report({"model_provider": {"type": "custom_plugin"}})
        self.assertFalse(report["schema"]["valid"])
        self.assertTrue(any(issue["code"] == "missing_plugin_spec" for issue in report["schema"]["issues"]))

    def test_framework_runtime_summary_contains_manifest_and_evaluation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "framework_customizable" / "profile.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["logs"]["run_dir"] = str(Path(temp_dir) / "logs")
            temp_profile = Path(temp_dir) / "profile.json"
            temp_profile.write_text(json.dumps(profile), encoding="utf-8")
            result = RuntimeOrchestrator(profile_path=str(temp_profile)).run(episodes=1, max_steps=6)
            payload = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
            self.assertIn("framework_manifest", payload)
            self.assertIn("platform_manifest", payload)
            self.assertIn("compatibility", payload)
            self.assertIn("evaluation", payload)
            self.assertIn("metrics", payload["evaluation"])

    def test_describe_outputs_framework_platform_and_compatibility(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = repo_root / "profiles" / "framework_customizable" / "profile.json"
        buffer = io.StringIO()
        original_argv = sys.argv
        try:
            sys.argv = ["ironengine_rl.describe", "--profile", str(profile_path)]
            with redirect_stdout(buffer):
                describe_module.main()
        finally:
            sys.argv = original_argv
        payload = json.loads(buffer.getvalue())
        self.assertIn("schema", payload)
        self.assertIn("framework_manifest", payload)
        self.assertIn("platform_manifest", payload)
        self.assertIn("compatibility", payload)

    def test_validate_cli_strict_mode_exits_for_invalid_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_profile = Path(temp_dir) / "invalid_profile.json"
            temp_profile.write_text(json.dumps({"model_provider": {"type": "custom_plugin"}}), encoding="utf-8")
            buffer = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = ["ironengine_rl.validate", "--profile", str(temp_profile), "--strict"]
                with redirect_stdout(buffer):
                    with self.assertRaises(SystemExit) as exit_ctx:
                        validate_module.main()
            finally:
                sys.argv = original_argv
            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_ctx.exception.code, 1)
            self.assertFalse(payload["schema"]["valid"])
