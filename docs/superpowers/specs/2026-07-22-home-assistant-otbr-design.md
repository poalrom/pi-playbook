# Home Assistant OpenThread Border Router Design

## Goal

Extend the Home Assistant Ansible role with an OpenThread Border Router (OTBR)
container for a Home Assistant Connect ZBT-2 that is already flashed with
OpenThread RCP firmware. Home Assistant will use this border router to create
the home's first Thread network.

## Scope

The role will deploy OTBR in the existing Home Assistant Docker Compose project,
configure the Raspberry Pi host for Thread routing, validate the required host
resources, and document the one-time Home Assistant UI setup.

The role will not flash the ZBT-2, edit Home Assistant's internal integration
store, create Matter devices, or migrate an existing Thread dataset. Those
operations are outside this change.

## Architecture

The Compose project will gain an `otbr` service based on the official
`openthread/border-router` image. OTBR will use host networking so it can route
IPv6 traffic and advertise the Thread mesh on the Raspberry Pi's `eth0`
infrastructure interface.

The ZBT-2 will be mapped only into OTBR. Its current direct mapping into the
`homeassistant` service will be removed so that one service owns the serial RCP.
The role will retain the existing unrelated `/dev/ttyUSB0` Home Assistant device
mapping.

OTBR will receive the minimum access described by the upstream container setup:

- the `NET_ADMIN` capability;
- `/dev/net/tun` for its Thread interface;
- the configured ZBT-2 serial device; and
- a persistent host directory mounted at `/data`.

The persistent directory will preserve the border-router identity and Thread
state across container recreation.

## Configuration

`group_vars/all.yml` will define the OTBR settings beneath
`home_assistant.thread`. This moves the machine-specific ZBT-2 by-id path out of
the Compose template. The configuration will include:

- `image`: `openthread/border-router:latest`;
- `device`: `/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_E072A1D74B14-if00`;
- `data_path`: `{{ home_assistant.config_path }}/otbr`;
- `backbone_interface`: `eth0`;
- `baudrate`: `460800`;
- `hardware_flow_control`: enabled;
- `rest_api.listen_address`: `127.0.0.1`;
- `rest_api.port`: `18081`;
- `web.listen_address`: `127.0.0.1`; and
- `web.port`: `18080`.

Both service ports deliberately avoid OTBR's default 8080/8081 pair. They are
configurable and loopback-only, so they are not exposed to the LAN or added to
UFW. Home Assistant can still reach the REST API because both containers use
host networking.

The RCP URL will use `spinel+hdlc+uart`, the configured device path inside the
container, 460800 baud, and hardware flow control. Compose will map the
configured host path to the stable container path `/dev/ttyZBT2`, which the RCP
URL will reference. These settings match the ZBT-2 OpenThread RCP firmware
definition.

## Host Networking

The role will manage a dedicated sysctl configuration containing the settings
required by the upstream OTBR Docker setup:

- `net.ipv4.ip_forward = 1`;
- `net.ipv6.conf.all.forwarding = 1`;
- `net.ipv6.conf.eth0.accept_ra = 2`; and
- `net.ipv6.conf.eth0.accept_ra_rt_info_max_plen = 64`.

The interface-specific keys will be rendered from
`home_assistant.thread.backbone_interface`, not hard-coded in the task file.
Changes will be applied before the Compose project starts.

The OTBR container manages the forwarding chains needed for Thread traffic.
No inbound UFW rule is required for either loopback-bound management port.

## Deployment Flow

The Home Assistant role will:

1. Verify that the configured backbone interface, ZBT-2 path, and
   `/dev/net/tun` exist.
2. Create the persistent OTBR data directory.
3. Render and apply the OTBR sysctl configuration.
4. Render the Compose project with Home Assistant, Mosquitto, and OTBR.
5. Start or reconcile the Compose project through the existing deployment task.
6. Wait for the loopback OTBR REST endpoint on port 18081.
7. Query the REST API to ensure it returns a valid response.
8. Display the URL `http://127.0.0.1:18081` and the remaining Home Assistant UI
   steps.

An unchanged playbook run will leave the sysctl file, persistent data, and
containers unchanged.

## Home Assistant Onboarding

Because this installation runs Home Assistant Container rather than Home
Assistant OS with Supervisor, OTBR will not install or configure the integration
automatically. After deployment, the operator will:

1. Add the **OpenThread Border Router** integration using
   `http://127.0.0.1:18081`.
2. Open the automatically available **Thread** integration.
3. Create and select the new Home Assistant Thread network as the preferred
   network.
4. Send the Thread credentials to the Home Assistant companion app before
   commissioning Matter-over-Thread devices.

No existing Thread credentials need to be imported.

## Failure Handling

The role must fail with a clear message when the configured serial device,
backbone interface, or TUN device is absent. Compose startup must fail if OTBR
cannot claim its configured loopback ports or communicate with the RCP.

The role will not report deployment success until the OTBR REST API responds.
Container logs remain the primary diagnostic source for serial, Spinel, or
Thread-routing failures. OTBR state remains recoverable after container
recreation through the persistent `/data` mount.

## Verification

Static verification will:

- render and parse the modified Jinja/YAML files;
- confirm the ZBT-2 is mapped only into OTBR;
- confirm the RCP URL contains 460800 baud and hardware flow control;
- confirm the REST and web interfaces use the configured non-default ports;
- confirm the management interfaces bind only to loopback; and
- run the repository's available Ansible syntax or lint checks.

Deployment verification will confirm:

- the managed sysctls have their expected runtime values;
- the `otbr` container is running;
- the `wpan0` interface is created;
- the REST API responds at `http://127.0.0.1:18081`; and
- the Home Assistant OTBR integration accepts that URL and exposes a new Thread
  network.
