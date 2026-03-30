# Custom Robots and Sensors

This guide explains what is required when adapting `IronEngine-RL` to a robot other than the ARMSmart reference platform. It also clarifies where additional sensor types belong in the framework and how users can manage them conveniently through profiles instead of scattering integration logic across the codebase.

## Where Sensors Fit in the Framework

`IronEngine-RL` already separates sensor integration into a few predictable surfaces:

- `platform.capabilities.observation_fields` declares the scalar or normalized feedback fields the robot exposes
- `Observation.sensors` carries those runtime values as the primary non-image feedback map
- `platform.capabilities.camera_roles` and the profile camera config describe image-producing sensors and their intended use
- `Observation.cameras` carries camera-like inputs as `CameraFrame` entries with roles, features, and detections
- `action_scheme.feedback_fields` tells users and plugins which feedback channels matter for command scheduling and policy logic
- safety policies, metrics, and repositories consume the normalized observation rather than needing to know each device driver directly

In practice, this means users should integrate most new sensors by normalizing them into either scalar feedback fields, camera-role feeds, or structured metadata, then manage them from the profile.

## Sensor Integration Map

| Sensor type | Best framework surface | Typical profile/config location | Notes |
| --- | --- | --- | --- |
| Depth camera | `cameras` plus `camera_roles` | `hardware.cameras` or `vision` section | Treat as a camera feed with a dedicated role such as `depth_front` or `depth_wrist`; expose derived range/alignment features through detections or sensor fields when useful |
| RGB camera | `cameras` plus `camera_roles` | `hardware.cameras` or `vision` section | Use roles such as `dash`, `claw`, `overview`, or `inspection` |
| LiDAR | `Observation.sensors` or camera-like metadata | `platform.capabilities.observation_fields` and adapter config | Most projects normalize LiDAR into obstacle distance, sector clearance, or collision-risk fields instead of pushing raw scans through the whole stack |
| Temperature | `Observation.sensors` | `platform.capabilities.observation_fields` | Good for battery, motor, or environment monitoring and safety thresholds |
| Humidity | `Observation.sensors` | `platform.capabilities.observation_fields` | Usually an environmental feedback field used for logging, task constraints, or environment quality checks |
| IMU | `Observation.sensors` | `platform.capabilities.observation_fields` | Already fits naturally as fields like `imu_roll_deg`, `imu_pitch_deg`, and `imu_yaw_deg` |
| Gesture sensor | `Observation.sensors` or `metadata` | `platform.capabilities.observation_fields` and adapter/plugin config | Represent recognized gestures or intent scores as normalized fields such as `gesture_open_hand_score` or `operator_stop_gesture` |
| Air quality sensor | `Observation.sensors` | `platform.capabilities.observation_fields` | Useful for environment-aware tasks, logging, or safety monitoring |
| Pressure sensor | `Observation.sensors` | `platform.capabilities.observation_fields` | Works well for gripper force, pneumatic state, barometric pressure, or contact confidence |
| Ranging sensor | `Observation.sensors` | `platform.capabilities.observation_fields` | Ultrasound, ToF, or IR range data usually becomes fields such as `front_range_m` or `claw_range_m` |
| Audio interface | `Observation.sensors`, `metadata`, or provider-side features | adapter config, custom plugin config, and optional `observation_fields` | Usually expose derived values such as wake-word score, sound direction, speech confidence, or alarm detection instead of raw audio streams |

## Minimum Hardware Requirements

### Sensors

A customized platform should expose the observation fields needed by the chosen task and model. Common inputs include:

- battery or power health
- collision or proximity indicators
- arm height and extension
- gripper state
- object offset or target alignment
- optional camera visibility features
- optional IMU, ranging, environmental, or operator-interface signals when the task depends on them

### Robot Interface

Your robot interface should provide a stable way to send actions and receive telemetry. Typical transport options are:

- `mock` for dry runs and safe validation
- `serial` for direct MCU or controller links
- `udp` for networked controllers or robot gateways

### MCUs and Controllers

A microcontroller or robot controller should be able to:

- accept structured commands at a predictable rate
- return telemetry in a repeatable schema
- identify connection loss or stale data
- expose safe defaults on startup and disconnect
- support emergency stop or passive stop behavior

## Software Contract Requirements

Your platform definition should describe:

- supported transport backends
- observation fields
- camera roles
- action channels
- safety features
- timing expectations
- an `action_scheme` when you want command, feedback, and results surfaced explicitly

## How Users Manage Sensors Easily

The easiest management pattern is to keep a single normalized contract in the profile and let adapters translate real device outputs into that contract.

1. list every scalar-like signal in `platform.capabilities.observation_fields`
2. group image-producing sensors in `camera_roles` and the camera config block
3. mirror the most important fields in `action_scheme.feedback_fields` so policy timing and debugging stay readable
4. keep sensor-specific driver details inside the transport, hardware adapter, or custom plugin instead of the model logic
5. add safety thresholds only for fields that should stop, slow, or warn during operation
6. mock the sensor values first, then move to hardware-in-the-loop, then to the real device

This keeps the user-facing configuration easy to edit while preserving a clean separation between device drivers and framework logic.

The updated template at `examples/hardware/custom_robots/template.profile.json` demonstrates this pattern with grouped `hardware.sensors` placeholders for IMU, LiDAR, ranging, environment, pressure, gesture, audio, and thermal signals.

If you want a copyable sensor-rich example instead of a blank template, start from `examples/hardware/custom_robots/multi_sensor_station.profile.json`. It shows how to declare a grouped sensor inventory, depth-camera roles, action-scheme feedback fields, and safety thresholds in one place.

If you want the same grouped sensor pattern plus explicit safety reactions and evaluation, use `examples/hardware/custom_robots/multi_sensor_guarded.profile.json`. That example adds a custom safety policy, a custom sensor-health metric, and named mock scenarios such as `guarded_nominal`, `front_range_stop`, `gesture_stop`, and `air_quality_warning`. Users can switch the active mock path just by changing `hardware.mock.active_scenario`.

## Practical Naming Guidance

Use stable, readable field names in profiles and adapters. For example:

- `imu_roll_deg`, `imu_pitch_deg`, `imu_yaw_deg`
- `front_range_m`, `claw_range_m`, `rear_clearance_m`
- `motor_temp_c`, `ambient_temp_c`, `humidity_pct`
- `air_quality_index`, `co2_ppm`
- `gripper_pressure_kpa`, `barometer_kpa`
- `operator_stop_gesture`, `gesture_confidence`
- `audio_alarm_score`, `speech_command_confidence`

Consistent names make it easier for models, tasks, metrics, safety policies, and repository summaries to share the same contract.

## Recommended Workflow

1. start from `examples/hardware/custom_robots/template.profile.json` or generate a new profile with `python -m ironengine_rl.scaffold`
2. define the platform capability contract, including all observation fields and camera roles
3. confirm the scaffolded or edited `action_scheme` matches your intended command schedule and feedback flow
4. group optional devices under a profile section such as `hardware.sensors` so users can enable or disable them without rewriting the rest of the contract
5. normalize advanced sensors such as LiDAR, ranging, IMU, audio, or environmental sensors into stable fields before exposing them to the rest of the runtime
6. add only the fields you actually want the policy, safety layer, or repository to consume
7. validate the profile with mock transport
8. add realistic mock telemetry and camera features
9. switch active mock scenarios to exercise guarded conditions before moving to HIL or real hardware
10. switch to HIL or real hardware only after compatibility checks pass
11. add custom plugins only when built-in modules are not enough

## Action-Scheme Hint

The scaffold now generates `action_scheme.command_channels` and `action_scheme.feedback_fields` automatically. Edit them when your robot uses a phased policy, limited actuator set, or custom sequencing constraints.

## Related Pages

- `docs/figure-7-1-mapping.md` for the architecture-level mapping
- `docs/profiles-and-configuration.md` for profile editing guidance
- `docs/anomaly-detection-and-safety.md` for safety-oriented feedback and anomaly routing patterns