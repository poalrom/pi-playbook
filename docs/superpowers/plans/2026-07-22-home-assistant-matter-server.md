# Home Assistant Matter Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a persistent standalone Matter Server beside Home Assistant and OTBR so Home Assistant Container can commission and control Matter-over-Thread devices.

**Architecture:** The existing Home Assistant Compose project gains a host-networked Matter Server using the stable upstream image. Ansible owns its configuration, persistent directory, startup validation, and operator documentation; Home Assistant's supported UI remains responsible for creating the Matter integration config entry.

**Tech Stack:** Ansible, Jinja2, Docker Compose, Home Assistant Container, Open Home Foundation Python Matter Server

## Global Constraints

- Do not add automated tests or test suites.
- Use `ghcr.io/matter-js/python-matter-server:stable`.
- Store controller state below the Home Assistant stack directory.
- Use configurable TCP port `5581`, not the upstream default `5580`.
- Use host networking so IPv6, multicast, and mDNS remain available.
- Do not edit Home Assistant `.storage` files.
- Deploy and run live checks under the user's explicit authorization.

---

### Task 1: Add the Matter Server service and lifecycle

**Files:**
- Modify: `group_vars/all.yml`
- Modify: `roles/home-assistant/templates/docker-compose.yml.j2`
- Modify: `roles/home-assistant/tasks/main.yml`

**Interfaces:**
- Consumes: the existing `home_assistant` variable mapping and Compose project.
- Produces: a `matter-server` container listening on `home_assistant.matter.port` with persistent state at `home_assistant.matter.data_path`.

- [ ] **Step 1: Add Matter Server variables**

Add this mapping beside `home_assistant.thread`:

```yaml
  matter:
    image: "ghcr.io/matter-js/python-matter-server:stable"
    data_path: "{{ home_assistant.config_path }}/matter"
    port: 5581
```

- [ ] **Step 2: Add preflight validation and persistent storage**

Add an `ansible.builtin.assert` that verifies the image is nonempty, the data
path is absolute, the port is in `1024..65535`, and the port differs from Home
Assistant, MQTT, OTBR REST, and OTBR web ports. Add an
`ansible.builtin.file` task creating `home_assistant.matter.data_path` as
`root:root` with mode `0755`.

- [ ] **Step 3: Add the Compose service**

Render this service in the existing Compose template:

```yaml
  matter-server:
    container_name: matter-server
    image: {{ home_assistant.matter.image }}
    restart: unless-stopped
    network_mode: host
    security_opt:
      - apparmor:unconfined
    volumes:
      - {{ home_assistant.matter.data_path }}:/data
    command:
      - --storage-path
      - /data
      - --paa-root-cert-dir
      - /data/credentials
      - --port
      - "{{ home_assistant.matter.port }}"
```

- [ ] **Step 4: Add startup verification**

After the Compose stack starts, add `ansible.builtin.wait_for` against
`127.0.0.1:{{ home_assistant.matter.port }}` with a 120-second timeout. Skip it
in Ansible check mode.

- [ ] **Step 5: Extend deployment output**

Display `ws://127.0.0.1:{{ home_assistant.matter.port }}/ws` and state that it
is the custom-container URL for the Matter integration.

- [ ] **Step 6: Run focused static verification**

Run:

```bash
git diff --check
ANSIBLE_CONFIG=/mnt/c/dev/pi-playbook/ansible.cfg \
  ansible-playbook -i inventory.yml site.yml --syntax-check \
  --tags home-assistant
```

Expected: both commands exit `0`; Ansible reports a valid playbook.

- [ ] **Step 7: Commit the role change**

```bash
git add group_vars/all.yml \
  roles/home-assistant/templates/docker-compose.yml.j2 \
  roles/home-assistant/tasks/main.yml
git commit -m "feat(ha): add Matter server service"
```

### Task 2: Document Matter-over-Thread onboarding

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the Matter Server WebSocket URL and existing Thread integration.
- Produces: a one-time UI and Companion-app onboarding procedure plus focused diagnostics.

- [ ] **Step 1: Add Matter integration setup**

Document adding the Matter integration, disabling automatic app installation,
and using `ws://127.0.0.1:5581/ws`.

- [ ] **Step 2: Add credential synchronization and commissioning**

Document Android `Sync Thread credentials`, iOS `Send credentials to phone`,
and commissioning from the Companion app. Warn users to settle on the Thread
dataset before pairing devices; the deployed dataset is currently
`Google-EBC4`.

- [ ] **Step 3: Add diagnostics and support boundary**

Document:

```bash
docker ps --filter name=matter-server
docker logs matter-server
curl http://127.0.0.1:5581/
```

State that Home Assistant OS is the supported Matter installation and the
standalone container is self-managed.

- [ ] **Step 4: Verify documentation and commit**

Run `git diff --check`, inspect the complete Home Assistant README section,
then commit:

```bash
git add README.md
git commit -m "docs: explain Matter over Thread onboarding"
```

### Task 3: Deploy and verify the live stack

**Files:**
- Inspect generated file: `/opt/stacks/home-assistant/compose.yml` on `raspberry-pi`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: a running Matter Server while preserving healthy Home Assistant, MQTT, and OTBR services.

- [ ] **Step 1: Run an Ansible check/diff deployment preview**

```bash
ANSIBLE_CONFIG=/mnt/c/dev/pi-playbook/ansible.cfg \
  ansible-playbook -i inventory.yml site.yml --tags home-assistant \
  --check --diff
```

Expected: the rendered Compose diff contains only the intended Matter Server
service and supporting directory/configuration changes.

- [ ] **Step 2: Deploy the Home Assistant role**

```bash
ANSIBLE_CONFIG=/mnt/c/dev/pi-playbook/ansible.cfg \
  ansible-playbook -i inventory.yml site.yml --tags home-assistant
```

Expected: the play completes with `failed=0` and the Matter Server wait task
succeeds.

- [ ] **Step 3: Validate rendered Compose**

Run `docker compose -f /opt/stacks/home-assistant/compose.yml config` on the
Raspberry Pi. Inspect the normalized Matter Server service for host networking,
persistent storage, AppArmor, and port `5581`.

- [ ] **Step 4: Verify the live services**

Confirm:

```bash
docker ps --filter name=matter-server
docker logs --tail 100 matter-server
curl --fail http://127.0.0.1:5581/
docker exec otbr ot-ctl state
curl --fail http://127.0.0.1:18081/node
docker exec homeassistant python -m homeassistant --script check_config --config /config
```

Expected: Matter Server remains running and serves its endpoint, OTBR is
attached or leader, its REST API returns node JSON, and Home Assistant config
validation exits `0`.

- [ ] **Step 5: Verify idempotence**

Run the deployment command a second time. Expected: `changed=0` and `failed=0`.

- [ ] **Step 6: Inspect final branch state**

Run `git status --short --branch`, `git log --oneline -5`, and
`git diff HEAD~3 --check`. Expected: the feature branch is clean and contains
the design, plan, implementation, and documentation commits.
