# Living Room PC MQTT Control Design

## Goal

Create one Home Assistant switch for the living-room Windows PC. The switch must:

- report whether HASS.Agent Satellite is connected to MQTT;
- start a powered-off PC with the existing ESPHome power-button entity;
- shut down Windows gracefully with the HASS.Agent Satellite shutdown command;
- expose the existing `switch.pc` entity to Yandex Smart Home; and
- never use an automatic hard-power-off fallback.

The combined entity treats “HASS.Agent Satellite is connected” as “PC is on.” This intentionally does not distinguish a powered-off PC from a PC whose Satellite service, network connection, or MQTT connection has failed.

## Inputs and Managed Entities

The design uses these existing inputs:

- HASS.Agent availability topic: `homeassistant/sensor/TV-satellite/availability`
- ESPHome startup button: `button.media_pc_power_switch_pc_power_button`
- HASS.Agent shutdown button: `button.tv_satellite_shutdown`

The playbook will manage these helper and public entities:

- `binary_sensor.living_room_pc_agent`: maps MQTT `online` and `offline` payloads to an on/off connectivity state.
- `timer.pc_starting`: provides a 15-second optimistic startup window.
- `switch.pc`: combines the state helper, timer, startup button, and shutdown button.

The helper should consume the availability topic directly. It must not infer connectivity from the MQTT button's displayed state.

## State Model

| Satellite state | Startup timer | Combined switch state |
| --- | --- | --- |
| `on` (`online`) | either | `on` |
| `off` (`offline`) | active | `on` |
| `off` (`offline`) | idle | `off` |
| `unknown` or `unavailable` | either | `unavailable` |

The Satellite state is authoritative after it becomes online. The timer only bridges the interval between pressing the physical power button and the Satellite service connecting.

When the 15-second timer expires while the Satellite remains offline, `switch.pc` returns to `off`.

## Turn-On Flow

When `switch.pc` receives a turn-on request:

1. If the Satellite state is unknown or unavailable, refuse the action because the current state is not trustworthy.
2. If the Satellite state is already online or the startup timer is active, do nothing.
3. If the ESPHome startup button is unavailable, refuse the action.
4. Otherwise, press the ESPHome startup button once and start `timer.pc_starting` for 15 seconds.

The combined switch reports `on` immediately after the timer starts. It remains on when the Satellite connects. If the Satellite does not connect before the timer expires, it reports `off` again.

## Turn-Off Flow

When `switch.pc` receives a turn-off request:

1. If the Satellite state is unknown or unavailable, refuse the action.
2. Cancel the startup timer if it is active.
3. If the Satellite is offline, do nothing because there is no connected Windows agent to shut down.
4. If `button.tv_satellite_shutdown` is unavailable, refuse the action without falling back to ESPHome.
5. Otherwise, press `button.tv_satellite_shutdown` once.

After the shutdown command, the combined switch stays on until the Satellite availability topic reports `offline`. This avoids claiming shutdown succeeded before HASS.Agent disconnects.

Turning off during the optimistic startup window cancels the timer but does not forcibly interrupt a PC that has already begun booting. If the PC later comes online, the user can issue another turn-off request.

## Availability and Failure Behavior

The combined switch uses state-first availability:

- a known Satellite state remains visible even if an actuator is unavailable;
- an unavailable actuator blocks only the action that requires it; and
- an unknown Satellite state makes the combined switch unavailable.

This preserves truthful state reporting and prevents a missing command entity from being mistaken for a powered-off PC.

The accepted limitation is that Satellite, network, or MQTT failure produces the same `offline` signal as a powered-off PC. ICMP is not retained as a second source of truth.

## Configuration Shape

The `home_assistant.yandex_smart_home.pc` variables will describe the three integration points rather than the previous ping-based model:

- MQTT availability topic;
- startup button entity ID;
- shutdown button entity ID; and
- startup duration set to `00:00:15`.

The old ping entity variable and five-second `homeassistant.update_entity` automation will be removed. README guidance about configuring and polling an ICMP Ping integration will be replaced with HASS.Agent Satellite setup and entity requirements.

## Yandex Smart Home

The public entity remains `switch.pc`. Its Yandex Smart Home name, room, `media_device` type, and split on/off behavior remain unchanged. Yandex Smart Home does not interact with the helper sensor or either underlying button directly.

## Verification

Before deployment:

- validate the Ansible and Jinja/YAML structure;
- confirm the rendered timer duration is 15 seconds;
- confirm no PC ping polling automation remains; and
- confirm the rendered template references the MQTT state helper and distinct startup/shutdown buttons.

After deployment:

- run Home Assistant configuration validation;
- verify retained/current `online` and `offline` payloads update the helper sensor;
- verify turn-on presses ESPHome once and starts the 15-second timer;
- verify Satellite connection keeps the combined switch on after the timer expires;
- verify turn-off presses only the HASS.Agent shutdown button;
- verify the switch remains on until Satellite reports offline; and
- verify unavailable controls never trigger an ESPHome shutdown fallback.

## Out of Scope

- ICMP fallback or cross-checking
- Wake-on-LAN
- Automatic hard shutdown
- Automatic retries of startup or shutdown commands
- Repairing or monitoring the HASS.Agent Satellite Windows service
