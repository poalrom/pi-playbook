# Home Assistant Matter Server Design

## Goal

Extend the existing Home Assistant Ansible role with a persistent standalone
Matter Server container so Home Assistant Container can commission and control
Matter-over-Thread devices through the existing OpenThread Border Router.

## Context

The role already runs Home Assistant, Mosquitto, and OpenThread Border Router
with host networking. OTBR is healthy and currently routes the `Google-EBC4`
Thread network through the Connect ZBT-2. Home Assistant Container has no
Supervisor, so it cannot install the supported Matter Server app and instead
needs the official standalone container.

Standalone Matter Server in Docker is provided by the upstream project but is
not an officially supported Home Assistant installation type. The Raspberry Pi
host must continue to provide working IPv6, multicast, and mDNS.

## Considered Approaches

### 1. Stable standalone Python Matter Server container (selected)

Run `ghcr.io/matter-js/python-matter-server:stable` in the existing Home
Assistant Compose project. This follows the upstream Docker guidance, uses the
stable Home Assistant-compatible WebSocket API, and keeps the deployment under
the existing Ansible role.

### 2. Migrate to Home Assistant OS

Home Assistant OS with the official Matter Server app is the supported and
best-tested configuration. It would require replacing the current Docker-based
host layout and is outside this change's scope.

### 3. Run the matter.js Matter Server beta

The replacement server is under active development and provides a compatible
API, but selecting a beta controller adds migration and commissioning risk
without a requirement that needs it.

## Configuration

Add a `home_assistant.matter` mapping to `group_vars/all.yml` containing:

- the stable upstream image;
- a persistent data path under the Home Assistant stack directory;
- TCP port `5581`, deliberately configurable and different from the upstream
  default port `5580`.

The role validates that the configured port is a non-privileged TCP port and
does not collide with the Home Assistant, MQTT, OTBR REST, or OTBR web ports.

## Compose Service

Add a `matter-server` service with:

- host networking for IPv6 and mDNS;
- `restart: unless-stopped`;
- `apparmor:unconfined`, as specified by the upstream container guidance;
- the configured persistent directory mounted at `/data`;
- an explicit command containing the default storage and PAA certificate
  arguments plus the configured non-default port.

The service does not mount D-Bus or claim a Bluetooth adapter. Home Assistant
commissions Matter devices through the Companion app on the user's phone, so
local Bluetooth commissioning in Matter Server is unnecessary.

## Ansible Lifecycle

The role creates the Matter Server data directory before rendering Compose.
The existing Compose deployment task creates or updates the container. After
Compose is applied, the role waits for the configured loopback port so a failed
startup stops the play with a clear error.

The Matter controller fabric remains in the persistent data directory across
container recreation and host reboots. That directory must be included in
normal Home Assistant stack backups.

## Home Assistant Integration

The role will not edit Home Assistant's internal `.storage` files. After the
first deployment, the user adds the Matter integration through Home Assistant's
supported UI, disables automatic app installation, and enters:

`ws://127.0.0.1:5581/ws`

The Thread network must be preferred and its credentials synchronized to the
Companion app before commissioning a new Matter-over-Thread device. The current
active dataset is `Google-EBC4`; replacing it with a new Thread dataset should
happen before any devices are commissioned.

## Documentation

Extend the Home Assistant README section with:

- the one-time Matter integration setup;
- Android and iOS Thread credential synchronization;
- Companion-app commissioning steps;
- focused Matter Server diagnostics;
- the standalone Docker support caveat.

## Verification

No automated tests or test suites will be added, as required by `AGENTS.md`.
Verification consists of:

1. Ansible playbook syntax checking.
2. Rendering the role in check/diff mode and inspecting the generated Compose
   configuration.
3. Running `docker compose config` against the deployed stack.
4. Deploying the role with explicit user authorization.
5. Confirming that the container stays running, port `5581` accepts
   connections, the WebSocket endpoint is advertised in logs, and OTBR remains
   healthy.
