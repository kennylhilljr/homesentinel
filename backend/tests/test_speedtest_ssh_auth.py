"""Tests for the paramiko-based Chester SSH auth in SpeedTestService.

2026-08-07: Added alongside the sshpass removal. Covers auth ordering
(key first, password fallback), the no-credentials guard, and that failures
are mapped to readable errors rather than raw tracebacks.
"""

import os
import socket
import sys
import types
import unittest
from unittest import mock

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.speedtest_service import SpeedTestService  # noqa: E402

OOKLA_JSON = (
    '{"download":{"bandwidth":40500000,"bytes":100},'
    '"upload":{"bandwidth":18912500,"bytes":50},'
    '"ping":{"latency":32.0,"jitter":7.5},'
    '"server":{"name":"Starry, Inc.","id":1234,"host":"speedtest.example"},'
    '"isp":"T-Mobile USA","interface":{"externalIp":"172.58.245.241"}}'
)

CHESTER_ENV = [
    "CHESTER_SSH_HOST",
    "CHESTER_SSH_PORT",
    "CHESTER_SSH_USERNAME",
    "CHESTER_SSH_PASSWORD",
    "CHESTER_SSH_KEY",
    "CHESTER_SSH_KEY_PASSPHRASE",
    "CHESTER_SSH_KNOWN_HOSTS",
]


class FakeChannel:
    def __init__(self, exit_status):
        self._exit_status = exit_status

    def recv_exit_status(self):
        return self._exit_status


class FakeStream:
    def __init__(self, payload, exit_status=0):
        self._payload = payload.encode()
        self.channel = FakeChannel(exit_status)

    def read(self):
        return self._payload


class BaseSpeedTestCase(unittest.TestCase):
    def setUp(self):
        # Stub DB: record inserts, return no history.
        self.stored = []
        conn = mock.Mock()
        conn.execute.side_effect = lambda sql, params=None: self.stored.append(params)
        db = types.SimpleNamespace(connection=conn)
        self.svc = SpeedTestService(db)
        self.svc._get_cellular_snapshot = lambda: {}
        self.svc._store_result = lambda result: self.stored.append(result)

        for var in CHESTER_ENV:
            os.environ.pop(var, None)
        self.addCleanup(lambda: [os.environ.pop(v, None) for v in CHESTER_ENV])


class TestCredentialResolution(BaseSpeedTestCase):
    def test_defaults(self):
        creds = self.svc._get_ssh_creds()
        self.assertEqual(creds["host"], "192.168.12.1")
        self.assertEqual(creds["port"], 22)
        self.assertEqual(creds["username"], "root")
        self.assertTrue(creds["key_path"].endswith("/.ssh/homesentinel_chester"))
        self.assertNotIn("~", creds["key_path"])
        self.assertNotIn("~", creds["known_hosts"])

    def test_env_overrides_win(self):
        os.environ["CHESTER_SSH_HOST"] = "10.0.0.9"
        os.environ["CHESTER_SSH_PORT"] = "2222"
        os.environ["CHESTER_SSH_KEY"] = "/tmp/somekey"
        creds = self.svc._get_ssh_creds()
        self.assertEqual(creds["host"], "10.0.0.9")
        self.assertEqual(creds["port"], 2222)
        self.assertEqual(creds["key_path"], "/tmp/somekey")

    def test_falls_back_to_chester_client_host_and_password(self):
        self.svc.chester_client = types.SimpleNamespace(
            host="192.168.5.1", password="hunter2"
        )
        creds = self.svc._get_ssh_creds()
        self.assertEqual(creds["host"], "192.168.5.1")
        self.assertEqual(creds["password"], "hunter2")


class TestAuthOrdering(BaseSpeedTestCase):
    def _run_with_fake_client(self, exists, connect_side_effect=None):
        fake_client = mock.MagicMock()
        fake_client.exec_command.return_value = (
            None,
            FakeStream(OOKLA_JSON),
            FakeStream(""),
        )
        if connect_side_effect:
            fake_client.connect.side_effect = connect_side_effect

        with mock.patch("paramiko.SSHClient", return_value=fake_client), mock.patch(
            "os.path.exists", side_effect=lambda p: exists
        ), mock.patch("pathlib.Path.mkdir"), mock.patch("pathlib.Path.touch"), mock.patch(
            "pathlib.Path.exists", return_value=True
        ):
            result = self.svc.run_speedtest()
        return result, fake_client

    def test_key_auth_used_when_key_present(self):
        result, client = self._run_with_fake_client(exists=True)
        self.assertIsNone(result["error"])
        self.assertEqual(result["download_mbps"], 324.0)
        self.assertEqual(result["upload_mbps"], 151.3)
        kwargs = client.connect.call_args.kwargs
        self.assertIn("key_filename", kwargs)
        self.assertNotIn("password", kwargs)
        # Never sweep in the user's other identities.
        self.assertFalse(kwargs["allow_agent"])
        self.assertFalse(kwargs["look_for_keys"])

    def test_password_used_when_no_key_file(self):
        os.environ["CHESTER_SSH_PASSWORD"] = "hunter2"
        result, client = self._run_with_fake_client(exists=False)
        self.assertIsNone(result["error"])
        kwargs = client.connect.call_args.kwargs
        self.assertEqual(kwargs["password"], "hunter2")
        self.assertNotIn("key_filename", kwargs)

    def test_password_fallback_after_key_rejected(self):
        os.environ["CHESTER_SSH_PASSWORD"] = "hunter2"
        attempts = [paramiko.AuthenticationException("key rejected"), None]
        result, client = self._run_with_fake_client(
            exists=True, connect_side_effect=attempts
        )
        self.assertIsNone(result["error"])
        self.assertEqual(client.connect.call_count, 2)
        self.assertEqual(client.connect.call_args.kwargs["password"], "hunter2")

    def test_no_key_and_no_password_is_a_clean_error(self):
        result, client = self._run_with_fake_client(exists=False)
        self.assertIn("no password configured", result["error"])
        self.assertIn("setup-chester-ssh-key.sh", result["error"])
        client.connect.assert_not_called()

    def test_network_failure_does_not_retry_with_password(self):
        os.environ["CHESTER_SSH_PASSWORD"] = "hunter2"
        err = paramiko.ssh_exception.NoValidConnectionsError(
            {("192.168.12.1", 22): socket.error("refused")}
        )
        result, client = self._run_with_fake_client(
            exists=True, connect_side_effect=err
        )
        self.assertEqual(client.connect.call_count, 1)
        self.assertIn("connection refused", result["error"].lower())


class TestErrorMapping(BaseSpeedTestCase):
    def _run(self, exec_return=None, connect_side_effect=None):
        fake_client = mock.MagicMock()
        fake_client.exec_command.return_value = exec_return or (
            None,
            FakeStream(OOKLA_JSON),
            FakeStream(""),
        )
        if connect_side_effect:
            fake_client.connect.side_effect = connect_side_effect
        with mock.patch("paramiko.SSHClient", return_value=fake_client), mock.patch(
            "os.path.exists", return_value=True
        ), mock.patch("pathlib.Path.mkdir"), mock.patch("pathlib.Path.touch"), mock.patch(
            "pathlib.Path.exists", return_value=True
        ):
            return self.svc.run_speedtest()

    def test_missing_speedtest_binary(self):
        result = self._run(
            exec_return=(None, FakeStream("", 127), FakeStream("speedtest: not found"))
        )
        self.assertIn("`speedtest` not found on Chester", result["error"])

    def test_auth_failure_message(self):
        result = self._run(
            connect_side_effect=paramiko.AuthenticationException("bad creds")
        )
        self.assertIn("SSH authentication failed", result["error"])

    def test_changed_host_key_is_reported_not_swallowed(self):
        key = paramiko.RSAKey.generate(2048)
        result = self._run(
            connect_side_effect=paramiko.BadHostKeyException("192.168.12.1", key, key)
        )
        self.assertIn("host key changed", result["error"])
        self.assertIn("homesentinel_known_hosts", result["error"])

    def test_timeout(self):
        result = self._run(connect_side_effect=socket.timeout())
        self.assertIn("timed out", result["error"])

    def test_connection_always_closed(self):
        fake_client = mock.MagicMock()
        fake_client.exec_command.return_value = (
            None,
            FakeStream(OOKLA_JSON),
            FakeStream(""),
        )
        with mock.patch("paramiko.SSHClient", return_value=fake_client), mock.patch(
            "os.path.exists", return_value=True
        ), mock.patch("pathlib.Path.mkdir"), mock.patch("pathlib.Path.touch"), mock.patch(
            "pathlib.Path.exists", return_value=True
        ):
            self.svc.run_speedtest()
        fake_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
