import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "tests"))

from config import (  # noqa: E402
    ConfigError,
    environment_variables,
    gateway_uris,
    resolve_listen_port,
    resolve_target,
)
from wire import (  # noqa: E402
    _ld,
    configuration,
    configuration_file,
    instance,
    uri,
    uri_slot,
)


class GatewayUriTests(unittest.TestCase):
    def test_a_single_uri_is_read(self):
        buf = configuration_file(
            gateway=instance(uri_slot(uri("192.168.200.1", 4041))),
        )
        self.assertEqual(gateway_uris(buf), [("192.168.200.1", 4041)])

    def test_several_uris_keep_file_order(self):
        buf = configuration_file(
            gateway=instance(
                uri_slot(uri("10.0.0.1", 1), uri("10.0.0.2", 2)),
            ),
        )
        self.assertEqual(
            gateway_uris(buf),
            [("10.0.0.1", 1), ("10.0.0.2", 2)],
        )

    def test_an_empty_file_has_no_uris(self):
        self.assertEqual(gateway_uris(b""), [])


class EnvTests(unittest.TestCase):
    def test_environment_variables_are_read(self):
        buf = configuration_file(
            config=configuration(TARGET="1.2.3.4:4040", LISTEN_PORT="9000"),
        )
        self.assertEqual(
            environment_variables(buf),
            {"TARGET": "1.2.3.4:4040", "LISTEN_PORT": "9000"},
        )

    def test_gateway_and_env_coexist(self):
        buf = configuration_file(
            gateway=instance(uri_slot(uri("192.168.200.1", 4041))),
            config=configuration(TARGET_PORT="443"),
        )
        self.assertEqual(gateway_uris(buf), [("192.168.200.1", 4041)])
        self.assertEqual(environment_variables(buf), {"TARGET_PORT": "443"})


class ResolveTests(unittest.TestCase):
    uris = [("192.168.200.1", 4041)]

    def test_default_is_the_config_gateway(self):
        self.assertEqual(resolve_target({}, self.uris), ("192.168.200.1", 4041))

    def test_TARGET_overrides_everything(self):
        self.assertEqual(
            resolve_target({"TARGET": "8.8.8.8:53"}, self.uris),
            ("8.8.8.8", 53),
        )

    def test_TARGET_PORT_keeps_the_config_host(self):
        """TLS port of the same node: the IP is still the bridge."""
        self.assertEqual(
            resolve_target({"TARGET_PORT": "443"}, self.uris),
            ("192.168.200.1", 443),
        )

    def test_TARGET_HOST_keeps_the_config_port(self):
        self.assertEqual(
            resolve_target({"TARGET_HOST": "10.9.8.7"}, self.uris),
            ("10.9.8.7", 4041),
        )

    def test_a_malformed_TARGET_is_refused(self):
        with self.assertRaises(ConfigError):
            resolve_target({"TARGET": "no-port"}, self.uris)

    def test_nothing_at_all_is_refused(self):
        with self.assertRaises(ConfigError):
            resolve_target({}, [])

    def test_listen_port_defaults_to_4040(self):
        self.assertEqual(resolve_listen_port({}), 4040)
        self.assertEqual(resolve_listen_port({"LISTEN_PORT": "9000"}), 9000)

    def test_TARGET_HOST_and_PORT_together(self):
        self.assertEqual(
            resolve_target(
                {"TARGET_HOST": "10.9.8.7", "TARGET_PORT": "443"},
                self.uris,
            ),
            ("10.9.8.7", 443),
        )

    def test_bracketed_ipv6_TARGET(self):
        self.assertEqual(
            resolve_target({"TARGET": "[2001:db8::1]:4040"}, self.uris),
            ("2001:db8::1", 4040),
        )

    def test_unknown_config_fields_are_ignored(self):
        buf = configuration_file(
            gateway=instance(uri_slot(uri("192.168.200.1", 4041))),
            config=configuration(LISTEN_PORT="9"),
        )
        buf += _ld(3, b"ignored-network")
        buf += _ld(4, b"ignored-sysresources")
        from config import environment_variables, gateway_uris

        self.assertEqual(gateway_uris(buf), [("192.168.200.1", 4041)])
        self.assertEqual(environment_variables(buf), {"LISTEN_PORT": "9"})


if __name__ == "__main__":
    unittest.main()
