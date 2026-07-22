import unittest
from copy import deepcopy
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
        template = Environment(
            undefined=StrictUndefined,
            trim_blocks=True,
        ).from_string(
            (
                ROOT
                / "roles/home-assistant/templates/docker-compose.yml.j2"
            ).read_text(encoding="utf-8")
        )
        render_vars = deepcopy(cls.group_vars["home_assistant"])
        render_vars["data_path"] = "/opt/stacks/home-assistant/config"
        render_vars["timezone"] = "Europe/Amsterdam"
        render_vars["mqtt"]["config_path"] = (
            "/opt/stacks/home-assistant/mosquitto/config"
        )
        render_vars["mqtt"]["data_path"] = (
            "/opt/stacks/home-assistant/mosquitto/data"
        )
        render_vars["thread"]["data_path"] = "/opt/stacks/home-assistant/otbr"
        cls.compose = yaml.safe_load(
            template.render(home_assistant=render_vars)
        )
        cls.tasks = yaml.safe_load(
            (ROOT / "roles/home-assistant/tasks/main.yml").read_text(
                encoding="utf-8"
            )
        )
        cls.tasks_by_name = {task["name"]: task for task in cls.tasks}

    def test_thread_configuration_uses_zbt2_and_non_default_ports(self):
        self.assertEqual(
            self.thread["device"],
            "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_E072A1D74B14-if00",
        )
        self.assertEqual(
            self.thread["data_path"],
            "{{ home_assistant.config_path }}/otbr",
        )
        self.assertEqual(self.thread["backbone_interface"], "eth0")
        self.assertEqual(self.thread["baudrate"], 460800)
        self.assertIs(self.thread["hardware_flow_control"], True)
        self.assertEqual(
            self.thread["rest_api"],
            {"listen_address": "127.0.0.1", "port": 18081},
        )
        self.assertEqual(
            self.thread["web"],
            {"listen_address": "127.0.0.1", "port": 18080},
        )

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
        self.assertEqual(
            otbr["volumes"],
            ["/opt/stacks/home-assistant/otbr:/data"],
        )
        self.assertEqual(environment["OT_INFRA_IF"], "eth0")
        self.assertEqual(environment["OT_THREAD_IF"], "wpan0")
        self.assertEqual(
            environment["OT_RCP_DEVICE"],
            "spinel+hdlc+uart:///dev/ttyZBT2?uart-baudrate=460800"
            "&uart-flow-control",
        )
        self.assertEqual(environment["OT_REST_LISTEN_ADDR"], "127.0.0.1")
        self.assertEqual(environment["OT_REST_LISTEN_PORT"], 18081)
        self.assertEqual(environment["OT_WEB_LISTEN_ADDR"], "127.0.0.1")
        self.assertEqual(environment["OT_WEB_LISTEN_PORT"], 18080)

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
        self.assertIs(interface["ansible.builtin.stat"]["follow"], True)
        conditions = validation["ansible.builtin.assert"]["that"]
        self.assertIn("home_assistant_thread_device.stat.ischr", conditions)
        self.assertIn("home_assistant_thread_tun.stat.ischr", conditions)
        self.assertIn("home_assistant_thread_backbone.stat.isdir", conditions)

    def test_role_prepares_otbr_storage_and_routing(self):
        directory = self.tasks_by_name[
            "Create OpenThread Border Router data directory"
        ]
        sysctl = self.tasks_by_name["Configure OpenThread routing sysctls"]
        self.assertEqual(
            directory["ansible.builtin.file"]["path"],
            "{{ home_assistant.thread.data_path }}",
        )
        self.assertEqual(
            sysctl["ansible.posix.sysctl"]["sysctl_file"],
            "/etc/sysctl.d/60-otbr.conf",
        )
        self.assertIs(sysctl["ansible.posix.sysctl"]["sysctl_set"], True)
        self.assertIs(sysctl["ansible.posix.sysctl"]["reload"], True)
        self.assertEqual(
            sysctl["loop"],
            [
                {"name": "net.ipv4.ip_forward", "value": "1"},
                {"name": "net.ipv6.conf.all.forwarding", "value": "1"},
                {
                    "name": (
                        "net.ipv6.conf."
                        "{{ home_assistant.thread.backbone_interface }}"
                        ".accept_ra"
                    ),
                    "value": "2",
                },
                {
                    "name": (
                        "net.ipv6.conf."
                        "{{ home_assistant.thread.backbone_interface }}"
                        ".accept_ra_rt_info_max_plen"
                    ),
                    "value": "64",
                },
            ],
        )

    def test_role_verifies_otbr_rest_api_and_thread_interface(self):
        wait = self.tasks_by_name[
            "Wait for OpenThread Border Router REST API"
        ]
        api = self.tasks_by_name["Verify OpenThread Border Router REST API"]
        interface = self.tasks_by_name["Verify OpenThread interface"]
        self.assertEqual(
            wait["ansible.builtin.wait_for"]["host"],
            "{{ home_assistant.thread.rest_api.listen_address }}",
        )
        self.assertEqual(
            wait["ansible.builtin.wait_for"]["port"],
            "{{ home_assistant.thread.rest_api.port }}",
        )
        self.assertEqual(
            api["ansible.builtin.uri"]["url"],
            "http://{{ home_assistant.thread.rest_api.listen_address }}:"
            "{{ home_assistant.thread.rest_api.port }}/node",
        )
        self.assertEqual(
            interface["ansible.builtin.command"]["argv"],
            ["ip", "link", "show", "dev", "wpan0"],
        )
        self.assertIs(interface["changed_when"], False)

    def test_readme_documents_otbr_setup_and_diagnostics(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("**OpenThread Border Router setup**", readme)
        self.assertIn("http://127.0.0.1:18081", readme)
        self.assertIn("home_assistant.thread.device", readme)
        self.assertIn("docker logs otbr", readme)
        self.assertIn("docker exec otbr ot-ctl state", readme)
        self.assertIn("Send credentials to phone", readme)


if __name__ == "__main__":
    unittest.main()
