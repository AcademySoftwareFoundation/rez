# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Tests for rez.utils.amqp
"""
import logging
import os
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from rez.tests.util import TestBase
from rez.utils.amqp import _publish_message, parse_host_and_port, set_pika_log_level
from rez.vendor.pika.exceptions import AMQPConnectionError


class TestParseHostAndPort(TestBase):
    """Tests for parse_host_and_port()."""

    def test_host_only(self) -> None:
        host, port = parse_host_and_port("mybroker.example.com")
        self.assertEqual(host, "mybroker.example.com")
        self.assertIsNone(port)

    def test_host_and_port(self) -> None:
        host, port = parse_host_and_port("localhost:5672")
        self.assertEqual(host, "localhost")
        self.assertEqual(port, 5672)

    def test_amqp_scheme(self) -> None:
        host, port = parse_host_and_port("amqp://mybroker.example.com:5672")
        self.assertEqual(host, "mybroker.example.com")
        self.assertEqual(port, 5672)

    def test_host_only_no_port_in_url(self) -> None:
        host, port = parse_host_and_port("mybroker.example.com")
        self.assertEqual(host, "mybroker.example.com")
        self.assertIsNone(port)


class TestPublishMessageStdout(TestBase):
    """Tests for _publish_message() with host='stdout'."""

    def test_stdout_returns_true(self) -> None:
        result = _publish_message(
            host="stdout",
            amqp_settings={},
            routing_key="REZ.CONTEXT",
            data={"action": "created"}
        )
        self.assertTrue(result)


class TestPublishMessageConnectionFailure(TestBase):
    """Tests for _publish_message() broker connection failure handling."""

    _amqp_settings = {
        "userid": "",
        "password": "",
        "connect_timeout": 1,
        "exchange_name": "rez",
        "exchange_routing_key": "REZ.CONTEXT",
        "message_delivery_mode": 1,
    }

    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_socket_error_returns_false(self, mock_conn, _mock_params) -> None:
        """socket.error on connect should return False, not raise."""
        mock_conn.side_effect = socket.error("connection refused")
        result = _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        self.assertFalse(result)

    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_amqp_connection_error_returns_false(self, mock_conn, _mock_params) -> None:
        """AMQPConnectionError on connect should return False, not raise."""
        mock_conn.side_effect = AMQPConnectionError("broker refused")
        result = _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        self.assertFalse(result)

    @patch("rez.utils.amqp.print_warning")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_warning_printed_when_host_configured(self, mock_conn, _mock_params, mock_warn) -> None:
        """When host arg is non-empty and broker is unreachable, print_warning."""
        mock_conn.side_effect = socket.error("connection refused")
        _publish_message(
            host="mybroker:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        mock_warn.assert_called_once()
        self.assertIn("Cannot connect", mock_warn.call_args[0][0])

    @patch("rez.utils.amqp.set_pika_log_level")
    @patch("rez.utils.amqp.print_debug")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_debug_printed_when_no_host_and_debug_enabled(
        self, mock_conn, _mock_params, mock_debug, _mock_set_level
    ) -> None:
        """Empty host + debug_context_tracking on: print_debug is called."""
        mock_conn.side_effect = socket.error("connection refused")
        self.update_settings({"debug_context_tracking": True})
        _publish_message(
            host="",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        mock_debug.assert_called_once()
        self.assertIn("Cannot connect", mock_debug.call_args[0][0])

    @patch("rez.utils.amqp.print_debug")
    @patch("rez.utils.amqp.print_warning")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_silent_when_no_host_and_debug_disabled(self, mock_conn, _mock_params, mock_warn, mock_debug) -> None:
        """Empty host + debug_context_tracking off: no logging at all."""
        mock_conn.side_effect = socket.error("connection refused")
        self.update_settings({"debug_context_tracking": False})
        _publish_message(
            host="",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        mock_debug.assert_not_called()
        mock_warn.assert_not_called()

    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_successful_publish_returns_true(self, mock_conn, _mock_params) -> None:
        """Successful connection and publish returns True."""
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel
        result = _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={"action": "created"}
        )
        self.assertTrue(result)
        mock_channel.basic_publish.assert_called_once()

    @patch("rez.utils.amqp.print_error")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_publish_failure_returns_false(self, mock_conn, _mock_params, _mock_error) -> None:
        """Exception during basic_publish returns False."""
        mock_conn.return_value.channel.return_value.basic_publish.side_effect = Exception("publish error")
        result = _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        self.assertFalse(result)

    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_credentials_passed_when_userid_set(self, mock_conn, _mock_params) -> None:
        """When userid is set in amqp_settings, PlainCredentials are used."""
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel
        settings_with_creds = dict(self._amqp_settings, userid="guest", password="guest")
        result = _publish_message(
            host="localhost:5672",
            amqp_settings=settings_with_creds,
            routing_key="REZ.CONTEXT",
            data={}
        )
        self.assertTrue(result)
        # ConnectionParameters should have been called with a credentials kwarg
        call_kwargs = _mock_params.call_args[1]
        self.assertIn("credentials", call_kwargs)

    @patch("rez.utils.amqp.set_pika_log_level")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_set_pika_log_level_called_when_debug_enabled(self, mock_conn, _mock_params, mock_set_level) -> None:
        """set_pika_log_level() is called inside _publish_message when debug_context_tracking is on."""
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel
        self.update_settings({"debug_context_tracking": True})
        _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        mock_set_level.assert_called_once()

    @patch("rez.utils.amqp.set_pika_log_level")
    @patch("rez.utils.amqp.ConnectionParameters")
    @patch("rez.utils.amqp.BlockingConnection")
    def test_set_pika_log_level_not_called_when_debug_disabled(self, mock_conn, _mock_params, mock_set_level) -> None:
        """set_pika_log_level() is NOT called when debug_context_tracking is off."""
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel
        self.update_settings({"debug_context_tracking": False})
        _publish_message(
            host="localhost:5672",
            amqp_settings=self._amqp_settings,
            routing_key="REZ.CONTEXT",
            data={}
        )
        mock_set_level.assert_not_called()


class TestPublishMessageTLS(TestBase):
    """Tests for TLS settings in _publish_message()."""

    _amqp_settings = TestPublishMessageConnectionFailure._amqp_settings

    def _connect(self, host, **settings):
        """Publish with BlockingConnection mocked; return the ConnectionParameters."""
        with patch("rez.utils.amqp.BlockingConnection") as mock_conn:
            result = _publish_message(
                host=host,
                amqp_settings=dict(self._amqp_settings, **settings),
                routing_key="REZ.CONTEXT",
                data={}
            )
        self.assertTrue(result)
        return mock_conn.call_args[0][0]

    def test_plaintext_without_amqps(self) -> None:
        for host in ("mybroker:5671", "amqp://mybroker:5671"):
            params = self._connect(host)
            self.assertIsNone(params.ssl_options)
            self.assertEqual(params.port, 5671)

    def test_amqps_scheme_verifies_server(self) -> None:
        params = self._connect("amqps://mybroker")
        self.assertEqual(params.host, "mybroker")
        self.assertEqual(params.port, 5671)
        self.assertEqual(params.ssl_options.server_hostname, "mybroker")
        context = params.ssl_options.context
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @patch("rez.utils.amqp.print_warning")
    def test_missing_ca_file_warns(self, mock_warn) -> None:
        with patch("rez.utils.amqp.BlockingConnection") as mock_conn:
            result = _publish_message(
                host="amqps://mybroker",
                amqp_settings=dict(self._amqp_settings, ssl_ca_file="/does/not/exist.pem"),
                routing_key="REZ.CONTEXT",
                data={}
            )
        self.assertFalse(result)
        mock_conn.assert_not_called()
        self.assertIn("Cannot connect", mock_warn.call_args[0][0])


class _FakeTruststoreContext(ssl.SSLContext):
    pass


class TestDefaultSSLContext(TestBase):
    """Which CAs an amqps:// connection trusts when ssl_ca_file is not set.

    truststore and certifi are optional, so they are faked in sys.modules;
    a None entry makes the import fail as if the package were not installed.
    """

    # Self-signed CA standing in for certifi's bundle.
    _CA_PEM = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIIBojCCAUmgAwIBAgIUD6j81XMKCUIcbkmHolZdaBdDUP8wCgYIKoZIzj0EAwIw\n"
        "HjEcMBoGA1UEAwwTcmV6IHRlc3QgY2VydGlmaSBDQTAgFw0yNjExMjEyMDEyMDJa\n"
        "GA8yMTI2MTAyODIwMTIwMlowHjEcMBoGA1UEAwwTcmV6IHRlc3QgY2VydGlmaSBD\n"
        "QTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABMqJ7XB1uZTdkFwE7aWNN5q2jt4j\n"
        "munEQmkXx404ZVpJmw6zK3uX0e2K/y0dFKlUBUFUMVo5Sv/quLNctvF8h6+jYzBh\n"
        "MB0GA1UdDgQWBBTo3OB/IcZaJD46hQRvCdYKm472yzAfBgNVHSMEGDAWgBTo3OB/\n"
        "IcZaJD46hQRvCdYKm472yzAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIB\n"
        "BjAKBggqhkjOPQQDAgNHADBEAiAWJpGh3WfCB6VQx8JaLBMil+WHKHqhLQswFSik\n"
        "A1hn4gIgZYaN8RjnODhVg3/i94VKitxwvelReDC5YZfvXgbsMx0=\n"
        "-----END CERTIFICATE-----\n"
    )
    _CA_CN = ((("commonName", "rez test certifi CA"),),)

    def setUp(self) -> None:
        super().setUp()
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False)
        f.write(self._CA_PEM)
        f.close()
        self.addCleanup(os.unlink, f.name)
        self.ca_file = f.name
        self.fake_truststore = MagicMock(SSLContext=_FakeTruststoreContext)
        self.fake_certifi = MagicMock(where=lambda: self.ca_file)

    def _context(self, modules, **settings):
        with patch.dict(sys.modules, modules), \
                patch("rez.utils.amqp.BlockingConnection") as mock_conn:
            _publish_message(
                host="amqps://mybroker",
                amqp_settings=dict(TestPublishMessageConnectionFailure._amqp_settings, **settings),
                routing_key="REZ.CONTEXT",
                data={}
            )
        return mock_conn.call_args[0][0].ssl_options.context

    def _trusts_test_ca(self, context) -> bool:
        return any(c["subject"] == self._CA_CN for c in context.get_ca_certs())

    def test_truststore_used_when_installed(self) -> None:
        context = self._context({"truststore": self.fake_truststore, "certifi": self.fake_certifi})
        self.assertIsInstance(context, _FakeTruststoreContext)

    def test_certifi_added_without_truststore(self) -> None:
        context = self._context({"truststore": None, "certifi": self.fake_certifi})
        self.assertNotIsInstance(context, _FakeTruststoreContext)
        self.assertTrue(self._trusts_test_ca(context))
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_python_defaults_without_either(self) -> None:
        context = self._context({"truststore": None, "certifi": None})
        self.assertIs(type(context), ssl.SSLContext)
        self.assertFalse(self._trusts_test_ca(context))
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_ssl_ca_file_overrides_both(self) -> None:
        other_ca = os.path.join(os.path.dirname(self.ca_file), "missing.pem")
        self.fake_certifi.where = lambda: other_ca
        context = self._context(
            {"truststore": self.fake_truststore, "certifi": self.fake_certifi},
            ssl_ca_file=self.ca_file
        )
        self.assertIs(type(context), ssl.SSLContext)
        self.assertEqual(len(context.get_ca_certs()), 1)
        self.assertTrue(self._trusts_test_ca(context))


class TestSetPikaLogLevel(TestBase):
    """Tests for set_pika_log_level()."""

    @patch("rez.utils.amqp.logging.getLogger")
    def test_sets_debug_when_context_tracking_debug_on(self, mock_get_logger) -> None:
        self.update_settings({"debug_context_tracking": True})
        set_pika_log_level()
        mock_get_logger.assert_called_with("rez.vendor.pika")
        mock_get_logger.return_value.setLevel.assert_called_with(logging.DEBUG)

    @patch("rez.utils.amqp.logging.getLogger")
    def test_no_change_when_context_tracking_debug_off(self, mock_get_logger) -> None:
        """When debug_context_tracking is off, level should not be changed to DEBUG."""
        self.update_settings({"debug_context_tracking": False})
        set_pika_log_level()
        # setLevel should not be called at all
        mock_get_logger.return_value.setLevel.assert_not_called()


class TestInitLogging(TestBase):
    """Tests for the REZ_LOGGING_CONF branch in rez._init_logging()."""

    # Minimal logging.config.fileConfig-compatible INI
    _LOGGING_INI = (
        "[loggers]\nkeys=root\n"
        "[handlers]\nkeys=console\n"
        "[formatters]\nkeys=\n"
        "[logger_root]\nlevel=WARNING\nhandlers=console\n"
        "[handler_console]\nclass=StreamHandler\nlevel=WARNING"
        "\nformatter=\nargs=(sys.stderr,)\n"
    )

    def _write_logging_conf(self) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        )
        f.write(self._LOGGING_INI)
        f.close()
        return f.name

    @patch("logging.config.fileConfig")
    def test_logging_conf_does_not_suppress_pika(self, mock_file_config) -> None:
        """REZ_LOGGING_CONF branch: rez does not touch the pika logger level.
        The user's config file is solely responsible for configuring it."""
        from rez import _init_logging

        conf_path = self._write_logging_conf()
        self.addCleanup(os.unlink, conf_path)

        pika_logger = logging.getLogger("rez.vendor.pika")
        original_level = pika_logger.level
        self.addCleanup(pika_logger.setLevel, original_level)
        pika_logger.setLevel(logging.NOTSET)

        with patch.dict(os.environ, {"REZ_LOGGING_CONF": conf_path}):
            _init_logging()

        # fileConfig was called with the correct arguments
        mock_file_config.assert_called_with(conf_path, disable_existing_loggers=False)
        # rez should not have changed the pika logger level
        self.assertEqual(pika_logger.level, logging.NOTSET)


if __name__ == "__main__":
    unittest.main()
