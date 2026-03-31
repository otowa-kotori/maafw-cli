"""Tests for CliContext routing — mock services, no real devices."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from maafw_cli.core.errors import MaafwError, ActionError
from maafw_cli.cli import CliContext
from maafw_cli.services.registry import service, DISPATCH


# ── test service functions ───────────────────────────────────────

@service(name="_test_action", needs_session=True,
         human=lambda r: f"did {r['action']}")
def _do_test_action(ctx, value: str = "ok") -> dict:
    return {"action": "test", "value": value}


@service(name="_test_fail", needs_session=True)
def _do_test_fail(ctx) -> dict:
    raise ActionError("test failure")


@service(name="_test_global", needs_session=False,
         human=lambda r: f"global {r['x']}")
def _do_test_global(x: int = 1) -> dict:
    return {"x": x}


@service(name="_test_global_fail", needs_session=False)
def _do_test_global_fail() -> dict:
    raise ActionError("global failure")


# ── daemon mode tests ────────────────────────────────────────────


class TestCliContextDaemon:
    """Tests with daemon mode (default and only path)."""

    def _make_ctx(self, **kwargs) -> CliContext:
        return CliContext(**kwargs)

    def test_run_daemon_routes_via_ipc(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "test", "value": "daemon"}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = ctx.run(_do_test_action, value="daemon")

        assert result["value"] == "daemon"
        mock_client.send.assert_called_once()

    def test_run_daemon_error_exits(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.side_effect = MaafwError("daemon error", exit_code=2)

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            with pytest.raises(SystemExit) as exc_info:
                ctx.run(_do_test_action)
            assert exc_info.value.code == 2

    def test_run_no_session_daemon_routes_via_ipc(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.return_value = {"x": 7}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = ctx.run(_do_test_global, x=7)

        assert result == {"x": 7}

    def test_run_no_session_error_exits(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.side_effect = MaafwError("global failure", exit_code=1)

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            with pytest.raises(SystemExit) as exc_info:
                ctx.run(_do_test_global_fail)
            assert exc_info.value.code == 1

    def test_run_raw_daemon(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "test", "value": "raw_d"}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = ctx.run_raw(_do_test_action, value="raw_d")
        assert result["value"] == "raw_d"

    def test_run_raw_no_session_daemon(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.return_value = {"x": 99}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = ctx.run_raw(_do_test_global, x=99)
        assert result == {"x": 99}


class TestCliContextOnSession:
    """--on <session> routes IPC to the named session."""

    def test_on_session_passed_to_daemon_send(self):
        ctx = CliContext(on="phone")
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "test", "value": "ok"}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            ctx.run(_do_test_action)

        # Verify session="phone" was passed to client.send
        call_kwargs = mock_client.send.call_args
        assert call_kwargs[1].get("session") == "phone" or call_kwargs[0][2] == "phone"


class TestOnSessionEnvVar:
    """MAAFW_SESSION env var should set --on via Click's envvar support."""

    def test_env_var_sets_on_session(self):
        from click.testing import CliRunner
        from maafw_cli.cli import cli

        test_runner = CliRunner(charset="utf-8")
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "click", "x": 100, "y": 200}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = test_runner.invoke(
                cli,
                ["click", "100,200"],
                env={"MAAFW_SESSION": "myphone"},
                catch_exceptions=False,
            )

        # Verify session="myphone" was passed
        call_kwargs = mock_client.send.call_args
        assert call_kwargs[1].get("session") == "myphone"

    def test_cli_flag_overrides_env_var(self):
        from click.testing import CliRunner
        from maafw_cli.cli import cli

        test_runner = CliRunner(charset="utf-8")
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "click", "x": 100, "y": 200}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = test_runner.invoke(
                cli,
                ["--on", "explicit", "click", "100,200"],
                env={"MAAFW_SESSION": "from_env"},
                catch_exceptions=False,
            )

        # --on flag should win over env var
        call_kwargs = mock_client.send.call_args
        assert call_kwargs[1].get("session") == "explicit"


# ── cleanup test services from DISPATCH ──────────────────────────

def teardown_module():
    for key in ["_test_action", "_test_fail", "_test_global", "_test_global_fail"]:
        DISPATCH.pop(key, None)
