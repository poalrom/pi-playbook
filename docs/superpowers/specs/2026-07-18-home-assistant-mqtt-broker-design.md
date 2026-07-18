# Home Assistant MQTT Broker Design

## Goal

Extend the existing Home Assistant Ansible role with an authenticated Eclipse
Mosquitto broker. The broker must be available to Home Assistant and devices on
the local network while remaining inaccessible from untrusted networks.

## Scope

The role will deploy and validate Mosquitto alongside Home Assistant in the
same Docker Compose project. It will manage broker configuration, persistent
data, authentication, firewall access, and operator documentation.

Home Assistant's MQTT integration will not be written into its internal config
store. The operator will complete that one-time setup in the Home Assistant UI.
TLS, public exposure, per-device accounts, and topic-level ACLs are outside this
change.

## Architecture

The existing Home Assistant Compose template will gain a `mosquitto` service
using a pinned Eclipse Mosquitto 2.1 image. Like Home Assistant, Mosquitto will
use host networking. It will listen on TCP port 1883, allowing Home Assistant to
connect through `127.0.0.1` and LAN devices to connect through the Raspberry
Pi's local address.

Host networking keeps MQTT traffic subject to the host's UFW policy. The
firewall role will allow port 1883 only from `network.local_subnet`; no reverse
proxy or public firewall rule will be created.

Mosquitto configuration and its hashed password file will be mounted read-only
from a role-managed config directory. Broker state will be stored in a separate
persistent data directory beneath the Home Assistant stack directory.

## Configuration and Authentication

`group_vars/all.yml` will define the non-secret MQTT settings beneath
`home_assistant.mqtt`, including the port and broker paths. The broker username
and password will be supplied by new variables in `vault.yml`, with documented
placeholders added to `vault-template.yml`.

The role will render a Mosquitto configuration that:

- creates an explicit MQTT listener on port 1883;
- rejects anonymous clients;
- enables persistence in the mounted data directory; and
- uses Mosquitto 2.1's password-file authentication plugin.

The role will generate a Mosquitto-compatible hashed password file from the
Vault credentials. Tasks that handle the plaintext password will suppress
sensitive Ansible output. The resulting file will have restrictive permissions
and will be readable by the Mosquitto container.

One shared authenticated account is sufficient for the initial Home Assistant
and LAN-device use case. Per-device identities and topic ACLs can be added later
without changing the container boundary.

## Deployment Flow

The Home Assistant role will:

1. Create the Mosquitto configuration and data directories.
2. Render the broker configuration.
3. Generate or update the hashed password file when credentials change.
4. Render the Compose project containing both Home Assistant and Mosquitto.
5. Start or recreate affected services through the existing Compose workflow.
6. Wait for Home Assistant and MQTT listener readiness.
7. Perform an authenticated MQTT publish/subscribe smoke test.

Configuration or credential changes will notify the existing Compose handler
so the broker reloads the managed state. An unchanged playbook run should not
regenerate credentials or restart services.

## Data Flow

Home Assistant will connect to `127.0.0.1:1883` using the Vault-managed
credentials entered through Settings > Devices & services > MQTT. Other trusted
devices will connect to `<network.pi_ip>:1883` with the same credentials.

Publishers send messages to Mosquitto, which authenticates the connection and
routes messages to subscribed clients. Persistent broker state survives
container recreation through the mounted data directory.

## Failure Handling

The role must fail before reporting success when:

- the broker configuration is invalid;
- the password file cannot be generated or read;
- TCP port 1883 does not become available; or
- the authenticated publish/subscribe smoke test fails.

Secrets must not appear in normal Ansible output. Home Assistant and Mosquitto
remain independently restartable services even though they share a Compose
project; Home Assistant's MQTT integration will reconnect after broker restarts.

## Verification

Static verification will render and parse the relevant YAML/Jinja templates
and run the repository's available Ansible syntax or lint checks. Deployment
verification will confirm:

- both containers are running;
- unauthenticated MQTT access is rejected;
- authenticated publish and subscribe succeeds;
- the UFW rule limits port 1883 to `network.local_subnet`; and
- a second unchanged Ansible run is idempotent.

The README will document the Vault variables, LAN endpoint, Home Assistant UI
setup, and a manual authenticated smoke-test command.
