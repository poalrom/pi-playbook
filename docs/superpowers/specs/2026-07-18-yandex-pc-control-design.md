# Yandex Smart Home PC Control Design

## Goal

Expose the living-room PC to Yandex Smart Home as one stateful device. The
device uses an ESP-backed momentary power button for control and an ICMP Ping
binary sensor for its authoritative online status.

This change updates only the Ansible-managed configuration in this repository.
It does not deploy or restart Home Assistant.

## Configuration inputs

Add a `pc` mapping below `home_assistant.yandex_smart_home` in
`group_vars/all.yml`. It contains deliberately invalid placeholder entity IDs
for the user to replace before deployment:

- ICMP Ping binary sensor entity ID
- ESP power button entity ID
- Yandex device name and room

The virtual Home Assistant entity is expected to be `switch.pc`.

## Home Assistant entities and behavior

Render `timer.pc_starting` with a 60-second duration. Render a template switch
named `PC` whose state is on when either the Ping sensor is on or the startup
timer is active.

Turning the switch on when Ping is off presses the ESP button and starts the
startup timer. Turning it on while Ping is already on does nothing.

Turning the switch off first cancels the startup timer. It presses the ESP
button only when Ping is on, avoiding a second button press while the PC is
still booting or already off. A short physical power-button press is assumed to
request a graceful operating-system shutdown.

The switch is unavailable when the Ping sensor has an unknown or unavailable
state, or when the ESP button is unavailable.

## Status refresh

Render an automation that calls `homeassistant.update_entity` for the Ping
binary sensor every five seconds. This reduces the delay between the PC becoming
network-reachable and the template switch receiving its authoritative state.

The Ping integration's automatic polling should be disabled manually before
deployment to avoid redundant polling. Its Consider Home option should be set
to approximately 10–15 seconds for prompt shutdown detection; these UI-owned
integration settings are outside this repository change.

## Yandex Smart Home mapping

Include `switch.pc` alongside the existing vacuum entity in the YAML entity
filter. Configure it with the requested name and room, the `media_device` type,
and separate on/off controls.

## Verification and deployment boundary

Verify the Jinja/Ansible syntax and inspect the rendered YAML locally where
possible. Do not execute the playbook, alter the live Home Assistant files,
restart containers, or deploy the configuration.
