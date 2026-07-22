# Home Assistant OpenThread Border Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone OpenThread Border Router service to the Home Assistant Ansible role for the Thread-flashed Home Assistant Connect ZBT-2.

**Architecture:** The existing Home Assistant Compose project gains the official upstream OTBR container with exclusive access to the ZBT-2, host networking, a persistent data mount, and loopback-only management endpoints. The role validates host devices, manages the required routing sysctls, verifies OTBR readiness, and leaves creation of the first Thread dataset to Home Assistant's UI.

**Tech Stack:** Ansible, Jinja2, Docker Compose, `openthread/border-router`, Python `unittest`, PyYAML

## Global Constraints

- Preserve the existing `/dev/ttyUSB0:/dev/ttyUSB0` mapping in the `homeassistant` service.
- Move `/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_E072A1D74B14-if00` into `home_assistant.thread.device`; map it only into OTBR as `/dev/ttyZBT2`.
- Use `eth0` as the OTBR infrastructure interface and `wpan0` as the Thread interface.
- Use 460800 baud with hardware flow control.
- Bind the OTBR web and REST interfaces only to `127.0.0.1` on configurable non-default ports 18080 and 18081.
- Persist OTBR state under `{{ home_assistant.config_path }}/otbr`.
- Do not add UFW rules, flash firmware, modify Home Assistant's internal storage, or create a Thread dataset outside the Home Assistant UI.
- Preserve unrelated user changes already present in the working tree.

---

## File Structure

- Create `tests/test_home_assistant_otbr.py`: static rendering and role-contract tests for configuration, Compose, host setup, readiness checks, and documentation.
- Modify `group_vars/all.yml`: define all machine-specific and operator-configurable OTBR settings under `home_assistant.thread`.
- Modify `roles/home-assistant/templates/docker-compose.yml.j2`: transfer ZBT-2 ownership from Home Assistant to the new OTBR service.
- Modify `roles/home-assistant/tasks/main.yml`: validate host resources, prepare persistent storage and sysctls, verify OTBR after deployment, and print onboarding guidance.
- Modify `README.md`: document deployment, HA integration setup, Thread network creation, and diagnostics.

---

### Task 1: OTBR Configuration and Compose Service

**Files:**

- Create: `tests/test_home_assistant_otbr.py`
- Modify: `group_vars/all.yml:119-145`
- Modify: `roles/home-assistant/templates/docker-compose.yml.j2:1-31`

**Interfaces:**

- Consumes: existing `home_assistant.config_path`, `home_assistant.data_path`, `home_assistant.mqtt`, and `home_assistant.timezone` variables.
- Produces: `home_assistant.thread.image`, `.device`, `.data_path`, `.backbone_interface`, `.baudrate`, `.hardware_flow_control`, `.rest_api`, and `.web`; Compose service `otbr` and container `otbr`.

- [ ] **Step 1: Write the failing configuration and Compose tests**

Create `tests/test_home_assistant_otbr.py`:

```python
import unittest
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined


ROOT = Path(__file__).resolve().parents[1]


class HomeAssistantOtbrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group_vars = yaml.safe_load(
            (ROOT / "group_vars/all.yml").read_text(encoding="utf-8")
        )
        cls.thread = cls.group_vars["home_assistant"]["thread"]
        template = Environment(undefined=StrictUndefined).from_string(
            (
                ROOT
                / "roles/home-assistant/templates/docker-compose.yml.j2"
            ).read_text(encoding="utf-8")
        )
        cls.compose = yaml.safe_load(
            template.render(home_assistant=cls.group_vars["home_assistant"])
        )

    def test_thread_configuration_uses_zbt2_and_non_default_ports(self):
        self.assertEqual(
            self.thread["device"],
            "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_E072A1D74B14-if00",
        )
        self.assertEqual(self.thread["data_path"], "{{ home_assistant.config_path }}/otbr")
        self.assertEqual(self.thread["backbone_interface"], "eth0")
        self.assertEqual(self.thread["baudrate"], 460800)
        self.assertIs(self.thread["hardware_flow_control"], True)
        self.assertEqual(self.thread["rest_api"], {"listen_address": "127.0.0.1", "port": 18081})
        self.assertEqual(self.thread["web"], {"listen_address": "127.0.0.1", "port": 18080})

    def test_zbt2_is_owned_only_by_otbr(self):
        services = self.compose["services"]
        home_assistant_devices = services["homeassistant"]["devices"]
        otbr_devices = services["otbr"]["devices"]
        self.assertEqual(home_assistant_devices, ["/dev/ttyUSB0:/dev/ttyUSB0"])
        self.assertIn("/dev/net/tun:/dev/net/tun", otbr_devices)
        self.assertIn(
            f'{self.thread["device"]}:/dev/ttyZBT2',
            otbr_devices,
        )

    def test_otbr_service_matches_network_and_rcp_contract(self):
        otbr = self.compose["services"]["otbr"]
        environment = otbr["environment"]
        self.assertEqual(otbr["container_name"], "otbr")
        self.assertEqual(otbr["image"], "openthread/border-router:latest")
        self.assertEqual(otbr["network_mode"], "host")
        self.assertEqual(otbr["cap_add"], ["NET_ADMIN"])
        self.assertEqual(otbr["volumes"], ["{{ home_assistant.config_path }}/otbr:/data"])
        self.assertEqual(environment["OT_INFRA_IF"], "eth0")
        self.assertEqual(environment["OT_THREAD_IF"], "wpan0")
        self.assertEqual(
            environment["OT_RCP_DEVICE"],
            "spinel+hdlc+uart:///dev/ttyZBT2?uart-baudrate=460800&uart-flow-control",
        )
        self.assertEqual(environment["OT_REST_LISTEN_ADDR"], "127.0.0.1")
        self.assertEqual(environment["OT_REST_LISTEN_PORT"], 18081)
        self.assertEqual(environment["OT_WEB_LISTEN_ADDR"], "127.0.0.1")
        self.assertEqual(environment["OT_WEB_LISTEN_PORT"], 18080)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: `ERROR` from `setUpClass` with `KeyError: 'thread'`.

- [ ] **Step 3: Add the configurable OTBR settings**

Insert this block after `home_assistant.mqtt` in `group_vars/all.yml`:

```yaml
  thread:
    image: "openthread/border-router:latest"
    device: "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_E072A1D74B14-if00"
    data_path: "{{ home_assistant.config_path }}/otbr"
    backbone_interface: "eth0"
    baudrate: 460800
    hardware_flow_control: true
    rest_api:
      listen_address: "127.0.0.1"
      port: 18081
    web:
      listen_address: "127.0.0.1"
      port: 18080
```

- [ ] **Step 4: Transfer the ZBT-2 and add the OTBR Compose service**

Remove the ZBT-2 by-id line from `homeassistant.devices`, leaving:

```yaml
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

Append this service after `mosquitto` in `roles/home-assistant/templates/docker-compose.yml.j2`:

```yaml

  otbr:
    container_name: otbr
    image: {{ home_assistant.thread.image }}
    restart: unless-stopped
    network_mode: host
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
      - {{ home_assistant.thread.device }}:/dev/ttyZBT2
    volumes:
      - {{ home_assistant.thread.data_path }}:/data
    environment:
      TZ: {{ home_assistant.timezone }}
      OT_RCP_DEVICE: >-
        spinel+hdlc+uart:///dev/ttyZBT2?uart-baudrate={{ home_assistant.thread.baudrate }}{% if home_assistant.thread.hardware_flow_control %}&uart-flow-control{% else %}&uart-init-deassert{% endif %}
      OT_INFRA_IF: {{ home_assistant.thread.backbone_interface }}
      OT_THREAD_IF: wpan0
      OT_REST_LISTEN_ADDR: {{ home_assistant.thread.rest_api.listen_address }}
      OT_REST_LISTEN_PORT: {{ home_assistant.thread.rest_api.port }}
      OT_WEB_LISTEN_ADDR: {{ home_assistant.thread.web.listen_address }}
      OT_WEB_LISTEN_PORT: {{ home_assistant.thread.web.port }}
```

- [ ] **Step 5: Run the tests to verify the Compose contract passes**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 6: Commit the configuration and Compose service**

```bash
git add tests/test_home_assistant_otbr.py group_vars/all.yml roles/home-assistant/templates/docker-compose.yml.j2
git commit -m "feat(ha): add OpenThread border router service"
```

---

### Task 2: Host Preparation and Runtime Verification

**Files:**

- Modify: `tests/test_home_assistant_otbr.py`
- Modify: `roles/home-assistant/tasks/main.yml:6-38,237-269,402-417`

**Interfaces:**

- Consumes: the `home_assistant.thread` variables and `otbr` service produced by Task 1.
- Produces: `/etc/sysctl.d/60-otbr.conf`, prepared `home_assistant.thread.data_path`, clear host-resource failures, REST readiness validation, `wpan0` validation, and deployment guidance.

- [ ] **Step 1: Add failing task-contract tests**

Add this helper in `HomeAssistantOtbrTests.setUpClass` after rendering `cls.compose`:

```python
        cls.tasks = yaml.safe_load(
            (ROOT / "roles/home-assistant/tasks/main.yml").read_text(encoding="utf-8")
        )
        cls.tasks_by_name = {task["name"]: task for task in cls.tasks}
```

Add these methods to `HomeAssistantOtbrTests`:

```python
    def test_role_validates_otbr_host_resources(self):
        device = self.tasks_by_name["Check OpenThread RCP device"]
        tun = self.tasks_by_name["Check OpenThread TUN device"]
        interface = self.tasks_by_name["Check OpenThread backbone interface"]
        validation = self.tasks_by_name["Validate OpenThread host resources"]
        self.assertEqual(
            device["ansible.builtin.stat"]["path"],
            "{{ home_assistant.thread.device }}",
        )
        self.assertIs(device["ansible.builtin.stat"]["follow"], True)
        self.assertEqual(tun["ansible.builtin.stat"]["path"], "/dev/net/tun")
        self.assertEqual(
            interface["ansible.builtin.stat"]["path"],
            "/sys/class/net/{{ home_assistant.thread.backbone_interface }}",
        )
        conditions = validation["ansible.builtin.assert"]["that"]
        self.assertIn("home_assistant_thread_device.stat.ischr", conditions)
        self.assertIn("home_assistant_thread_tun.stat.ischr", conditions)
        self.assertIn("home_assistant_thread_backbone.stat.isdir", conditions)

    def test_role_prepares_otbr_storage_and_routing(self):
        directory = self.tasks_by_name["Create OpenThread Border Router data directory"]
        sysctl = self.tasks_by_name["Configure OpenThread routing sysctls"]
        self.assertEqual(
            directory["ansible.builtin.file"]["path"],
            "{{ home_assistant.thread.data_path }}",
        )
        self.assertEqual(sysctl["ansible.posix.sysctl"]["sysctl_file"], "/etc/sysctl.d/60-otbr.conf")
        self.assertIs(sysctl["ansible.posix.sysctl"]["sysctl_set"], True)
        self.assertIs(sysctl["ansible.posix.sysctl"]["reload"], True)
        self.assertEqual(
            sysctl["loop"],
            [
                {"name": "net.ipv4.ip_forward", "value": "1"},
                {"name": "net.ipv6.conf.all.forwarding", "value": "1"},
                {
                    "name": "net.ipv6.conf.{{ home_assistant.thread.backbone_interface }}.accept_ra",
                    "value": "2",
                },
                {
                    "name": "net.ipv6.conf.{{ home_assistant.thread.backbone_interface }}.accept_ra_rt_info_max_plen",
                    "value": "64",
                },
            ],
        )

    def test_role_verifies_otbr_rest_api_and_thread_interface(self):
        wait = self.tasks_by_name["Wait for OpenThread Border Router REST API"]
        api = self.tasks_by_name["Verify OpenThread Border Router REST API"]
        interface = self.tasks_by_name["Verify OpenThread interface"]
        self.assertEqual(wait["ansible.builtin.wait_for"]["host"], "{{ home_assistant.thread.rest_api.listen_address }}")
        self.assertEqual(wait["ansible.builtin.wait_for"]["port"], "{{ home_assistant.thread.rest_api.port }}")
        self.assertEqual(
            api["ansible.builtin.uri"]["url"],
            "http://{{ home_assistant.thread.rest_api.listen_address }}:{{ home_assistant.thread.rest_api.port }}/node",
        )
        self.assertEqual(interface["ansible.builtin.command"]["argv"], ["ip", "link", "show", "dev", "wpan0"])
        self.assertIs(interface["changed_when"], False)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: three `ERROR` results containing missing task names such as `KeyError: 'Check OpenThread RCP device'`.

- [ ] **Step 3: Add host validation, storage, and sysctl tasks**

Insert these tasks after `Create Home Assistant config directory` and before the Mosquitto tasks:

```yaml
- name: Check OpenThread RCP device
  ansible.builtin.stat:
    path: "{{ home_assistant.thread.device }}"
    follow: true
  register: home_assistant_thread_device

- name: Check OpenThread TUN device
  ansible.builtin.stat:
    path: /dev/net/tun
  register: home_assistant_thread_tun

- name: Check OpenThread backbone interface
  ansible.builtin.stat:
    path: "/sys/class/net/{{ home_assistant.thread.backbone_interface }}"
  register: home_assistant_thread_backbone

- name: Validate OpenThread host resources
  ansible.builtin.assert:
    that:
      - home_assistant_thread_device.stat.exists
      - home_assistant_thread_device.stat.ischr
      - home_assistant_thread_tun.stat.exists
      - home_assistant_thread_tun.stat.ischr
      - home_assistant_thread_backbone.stat.exists
      - home_assistant_thread_backbone.stat.isdir
    fail_msg: >-
      OpenThread requires character devices {{ home_assistant.thread.device }}
      and /dev/net/tun plus backbone interface
      {{ home_assistant.thread.backbone_interface }}.

- name: Create OpenThread Border Router data directory
  ansible.builtin.file:
    path: "{{ home_assistant.thread.data_path }}"
    state: directory
    owner: root
    group: root
    mode: "0755"

- name: Configure OpenThread routing sysctls
  ansible.posix.sysctl:
    name: "{{ item.name }}"
    value: "{{ item.value }}"
    state: present
    sysctl_file: /etc/sysctl.d/60-otbr.conf
    sysctl_set: true
    reload: true
  loop:
    - { name: "net.ipv4.ip_forward", value: "1" }
    - { name: "net.ipv6.conf.all.forwarding", value: "1" }
    - name: "net.ipv6.conf.{{ home_assistant.thread.backbone_interface }}.accept_ra"
      value: "2"
    - name: "net.ipv6.conf.{{ home_assistant.thread.backbone_interface }}.accept_ra_rt_info_max_plen"
      value: "64"
```

- [ ] **Step 4: Add REST and interface verification tasks**

Insert these tasks after `Apply desired MQTT broker state` and before `Wait for Home Assistant to be ready`:

```yaml
- name: Wait for OpenThread Border Router REST API
  ansible.builtin.wait_for:
    host: "{{ home_assistant.thread.rest_api.listen_address }}"
    port: "{{ home_assistant.thread.rest_api.port }}"
    delay: 2
    timeout: 120
  when: not ansible_check_mode

- name: Verify OpenThread Border Router REST API
  ansible.builtin.uri:
    url: >-
      http://{{ home_assistant.thread.rest_api.listen_address }}:{{ home_assistant.thread.rest_api.port }}/node
    method: GET
    status_code: 200
    return_content: true
  register: home_assistant_thread_rest_api
  changed_when: false
  failed_when: >-
    home_assistant_thread_rest_api.status != 200 or
    home_assistant_thread_rest_api.json is not mapping
  when: not ansible_check_mode

- name: Verify OpenThread interface
  ansible.builtin.command:
    argv:
      - ip
      - link
      - show
      - dev
      - wpan0
  changed_when: false
  when: not ansible_check_mode
```

Add these messages to the final `Display Home Assistant access information` list:

```yaml
      - >-
        OpenThread REST API:
        http://{{ home_assistant.thread.rest_api.listen_address }}:{{ home_assistant.thread.rest_api.port }}
      - >-
        Add the OpenThread Border Router integration with that URL, then use
        the Thread integration to create and prefer the new Home Assistant network.
```

- [ ] **Step 5: Run the complete role-contract test suite**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: `Ran 6 tests` and `OK`.

- [ ] **Step 6: Commit host preparation and runtime checks**

```bash
git add tests/test_home_assistant_otbr.py roles/home-assistant/tasks/main.yml
git commit -m "feat(ha): prepare and verify OpenThread routing"
```

---

### Task 3: Operator Documentation

**Files:**

- Modify: `tests/test_home_assistant_otbr.py`
- Modify: `README.md:308-380`

**Interfaces:**

- Consumes: REST endpoint `http://127.0.0.1:18081`, container name `otbr`, and configuration key `home_assistant.thread.device` from Tasks 1 and 2.
- Produces: one-time Home Assistant onboarding and diagnostic instructions for the operator.

- [ ] **Step 1: Add a failing documentation test**

Add this method to `HomeAssistantOtbrTests`:

```python
    def test_readme_documents_otbr_setup_and_diagnostics(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("**OpenThread Border Router setup**", readme)
        self.assertIn("http://127.0.0.1:18081", readme)
        self.assertIn("home_assistant.thread.device", readme)
        self.assertIn("docker logs otbr", readme)
        self.assertIn("docker exec otbr ot-ctl state", readme)
        self.assertIn("Send credentials to phone", readme)
```

- [ ] **Step 2: Run the documentation test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr.HomeAssistantOtbrTests.test_readme_documents_otbr_setup_and_diagnostics -v
```

Expected: `FAIL` because `**OpenThread Border Router setup**` is absent.

- [ ] **Step 3: Document OTBR deployment and Home Assistant onboarding**

Insert this section after the MQTT broker setup and before HACS setup in `README.md`:

```markdown
**OpenThread Border Router setup**:

The Home Assistant role runs the official OpenThread Border Router container
with the Thread-flashed Connect ZBT-2. Before deployment, confirm the stable
serial path in `home_assistant.thread.device` and keep the adapter connected to
the Raspberry Pi through its USB extension cable.

After running the role:

1. Go to **Settings → Devices & services → Add integration**.
2. Select **OpenThread Border Router** and enter `http://127.0.0.1:18081`.
3. Open the **Thread** integration and create/select the new Home Assistant
   Thread network as the preferred network.
4. In the Home Assistant companion app, open the Thread integration and select
   **Send credentials to phone** before adding Matter-over-Thread devices.

The REST API and optional OTBR web interface listen only on the Raspberry Pi's
loopback interface, on ports `18081` and `18080`. They are not exposed through
UFW or the reverse proxy.

Useful diagnostics on the Raspberry Pi:

```bash
docker logs otbr
docker exec otbr ot-ctl state
docker exec otbr ot-ctl dataset active
ip link show wpan0
curl http://127.0.0.1:18081/node
```
```

- [ ] **Step 4: Run the full test suite**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: `Ran 7 tests` and `OK`.

- [ ] **Step 5: Commit the operator documentation**

```bash
git add tests/test_home_assistant_otbr.py README.md
git commit -m "docs: explain Home Assistant Thread onboarding"
```

---

### Task 4: Final Static Verification

**Files:**

- Verify: `tests/test_home_assistant_otbr.py`
- Verify: `group_vars/all.yml`
- Verify: `roles/home-assistant/templates/docker-compose.yml.j2`
- Verify: `roles/home-assistant/tasks/main.yml`
- Verify: `README.md`

**Interfaces:**

- Consumes: all deliverables from Tasks 1 through 3.
- Produces: evidence that the implementation renders, parses, and passes Ansible syntax validation without deploying to the Raspberry Pi.

- [ ] **Step 1: Run the focused unit tests from a clean process**

Run:

```bash
python3 -m unittest tests.test_home_assistant_otbr -v
```

Expected: seven passing tests and final output `OK`.

- [ ] **Step 2: Run Ansible syntax validation with the repository configuration explicitly selected**

Run:

```bash
ANSIBLE_CONFIG="$PWD/ansible.cfg" ansible-playbook -i inventory.yml site.yml --syntax-check
```

Expected: exit code 0 and `playbook: site.yml`. This command validates syntax only and does not connect to or change the Raspberry Pi.

- [ ] **Step 3: Check whitespace and the final change scope**

Run:

```bash
git diff --check HEAD~3..HEAD
git status --short
```

Expected: `git diff --check` exits 0. `git status --short` shows no implementation files and only any unrelated pre-existing user changes that were intentionally left uncommitted.

- [ ] **Step 4: Record deployment commands without running them**

The implementation handoff must provide these commands, but must not execute them without the operator explicitly authorizing changes to the Raspberry Pi:

```bash
ansible-playbook -i inventory.yml site.yml --tags home-assistant
docker logs otbr
curl http://127.0.0.1:18081/node
```

Expected after an operator-authorized deployment: the role completes, `docker logs otbr` shows a running `otbr-agent`, and the REST request returns JSON.
