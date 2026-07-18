from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[1]


def render(path: str, **context: object) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    environment = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    return environment.from_string(source).render(**context)


class HomeAssistantMqttConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        all_vars = yaml.safe_load(
            (ROOT / "group_vars/all.yml").read_text(encoding="utf-8")
        )
        self.mqtt = all_vars["home_assistant"]["mqtt"]
        self.rendered_home_assistant = {
            "data_path": "/opt/stacks/home-assistant/config",
            "timezone": "Europe/Amsterdam",
            "mqtt": {
                "image": "eclipse-mosquitto:2.1.2",
                "port": 1883,
                "config_path": "/opt/stacks/home-assistant/mosquitto/config",
                "data_path": "/opt/stacks/home-assistant/mosquitto/data",
            },
        }

    def test_group_vars_define_pinned_mqtt_defaults(self) -> None:
        self.assertEqual(self.mqtt["image"], "eclipse-mosquitto:2.1.2")
        self.assertEqual(self.mqtt["port"], 1883)
        self.assertEqual(
            self.mqtt["config_path"],
            "{{ docker.stacks_directory }}/home-assistant/mosquitto/config",
        )
        self.assertEqual(
            self.mqtt["data_path"],
            "{{ docker.stacks_directory }}/home-assistant/mosquitto/data",
        )

    def test_mosquitto_configuration_requires_plugin_authentication(self) -> None:
        rendered = render(
            "roles/home-assistant/templates/mosquitto.conf.j2",
            home_assistant=self.rendered_home_assistant,
        )
        self.assertIn("listener 1883", rendered)
        self.assertIn("listener_allow_anonymous false", rendered)
        self.assertIn(
            "global_plugin /usr/lib/mosquitto_password_file.so", rendered
        )
        self.assertIn(
            "plugin_opt_password_file /mosquitto/config/password_file", rendered
        )
        self.assertIn("persistence true", rendered)
        self.assertIn("persistence_location /mosquitto/data/", rendered)
        self.assertNotIn("\npassword_file ", rendered)

    def test_compose_adds_host_networked_mosquitto(self) -> None:
        rendered = render(
            "roles/home-assistant/templates/docker-compose.yml.j2",
            home_assistant=self.rendered_home_assistant,
        )
        compose = yaml.safe_load(rendered)
        mosquitto = compose["services"]["mosquitto"]
        self.assertEqual(mosquitto["image"], "eclipse-mosquitto:2.1.2")
        self.assertEqual(mosquitto["network_mode"], "host")
        self.assertEqual(mosquitto["restart"], "unless-stopped")
        self.assertIn(
            "/opt/stacks/home-assistant/mosquitto/config/mosquitto.conf:"
            "/mosquitto/config/mosquitto.conf:ro",
            mosquitto["volumes"],
        )
        self.assertIn(
            "/opt/stacks/home-assistant/mosquitto/config/password_file:"
            "/mosquitto/config/password_file:ro",
            mosquitto["volumes"],
        )
        self.assertIn(
            "/opt/stacks/home-assistant/mosquitto/data:/mosquitto/data",
            mosquitto["volumes"],
        )

    def test_vault_template_documents_mqtt_credentials(self) -> None:
        vault_template = (ROOT / "vault-template.yml").read_text(encoding="utf-8")
        self.assertIn('mqtt_broker_username: "homeassistant"', vault_template)
        self.assertIn('mqtt_broker_password: "CHANGE_ME"', vault_template)

    def test_firewall_allows_mqtt_from_lan_only(self) -> None:
        firewall = (ROOT / "roles/firewall/tasks/main.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('port: "{{ home_assistant.mqtt.port }}"', firewall)
        self.assertIn('src: "{{ network.local_subnet }}"', firewall)
        self.assertIn('comment: "MQTT broker - local network only"', firewall)

    def test_role_orchestrates_and_verifies_mqtt(self) -> None:
        tasks = (ROOT / "roles/home-assistant/tasks/main.yml").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            "Create Mosquitto directories",
            "Create Mosquitto configuration",
            "Calculate MQTT credentials checksum",
            "Generate Mosquitto password file",
            "Protect Mosquitto password file",
            "Save MQTT credentials checksum",
            "Apply Home Assistant stack configuration changes",
            "Wait for MQTT broker to be ready",
            "Verify MQTT rejects anonymous clients",
            "Verify authenticated MQTT publish and subscribe",
            "no_log: true",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, tasks)

    def test_role_recovers_a_missing_mosquitto_password_file(self) -> None:
        tasks = yaml.safe_load(
            (ROOT / "roles/home-assistant/tasks/main.yml").read_text(
                encoding="utf-8"
            )
        )
        tasks_by_name = {task["name"]: task for task in tasks}
        task_name = "Check Mosquitto password file"

        self.assertIn(task_name, tasks_by_name)
        password_file_check = tasks_by_name[task_name]
        self.assertEqual(
            password_file_check["ansible.builtin.stat"]["path"],
            "{{ home_assistant.mqtt.config_path }}/password_file",
        )
        self.assertEqual(
            password_file_check["register"],
            "home_assistant_mqtt_password_file",
        )

        credentials_changed = tasks_by_name[
            "Determine whether MQTT credentials changed"
        ]["ansible.builtin.set_fact"][
            "home_assistant_mqtt_credentials_changed"
        ]
        self.assertIn(
            "not home_assistant_mqtt_password_file.stat.exists",
            credentials_changed,
        )

    def test_authenticated_smoke_test_is_secret_safe_and_bounded(self) -> None:
        tasks = yaml.safe_load(
            (ROOT / "roles/home-assistant/tasks/main.yml").read_text(
                encoding="utf-8"
            )
        )
        tasks_by_name = {task["name"]: task for task in tasks}
        smoke_test = tasks_by_name[
            "Verify authenticated MQTT publish and subscribe"
        ]
        argv = smoke_test["ansible.builtin.command"]["argv"]
        command = argv[-1]

        self.assertNotIn("async", smoke_test)
        self.assertNotIn("poll", smoke_test)
        self.assertIs(smoke_test["no_log"], True)
        self.assertEqual(
            argv[7:13], ["timeout", "-k", "5", "15", "sh", "-ec"]
        )
        self.assertIn(
            'smoke_test_token="$(cat /proc/sys/kernel/random/uuid)"', command
        )
        self.assertIn(
            'smoke_test_topic="ansible/mqtt-smoke-test/$smoke_test_token"',
            command,
        )
        self.assertIn(
            'smoke_test_payload="ansible-ok-$smoke_test_token"', command
        )
        self.assertIn("cleanup()", command)
        self.assertIn('trap \'fallback_cleanup "$?"\' EXIT', command)
        self.assertIn("trap 'fallback_cleanup 124' TERM", command)
        self.assertIn('-m "$smoke_test_payload" -r', command)
        self.assertIn("-n -r", command)
        self.assertNotRegex(command, r"(?<!\\)\n\s+-(?:u|t)\b")
        self.assertIn('received_payload="$(mosquitto_sub', command)
        self.assertLess(
            command.index("mosquitto_pub"), command.index("mosquitto_sub")
        )
        self.assertIn(
            'test "$received_payload" = "$smoke_test_payload"; '
            "cleanup; trap - EXIT TERM",
            command,
        )
        self.assertNotIn("subscriber_pid", command)
        self.assertNotIn("sleep 1", command)


if __name__ == "__main__":
    unittest.main()
