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
        template = Environment(undefined=StrictUndefined).from_string(
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


if __name__ == "__main__":
    unittest.main()
