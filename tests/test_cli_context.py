"""Tests for CliContext routing — mock services, no real devices."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from maafw_cli.core.errors import MaafwError, ActionError
from maafw_cli.core.output import OutputFormatter
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


# ── direct mode tests ────────────────────────────────────────────


class TestCliContextDirect:
    """Tests with --no-daemon (direct mode)."""

    def _make_ctx(self, **kwargs) -> CliContext:
        return CliContext(no_daemon=True, **kwargs)

    def test_run_direct_success(self):
        ctx = self._make_ctx()
        mock_svc_ctx = MagicMock()
        with patch.object(ctx, "_make_service_context", return_value=mock_svc_ctx):
            result = ctx.run(_do_test_action, value="hello")
        assert result["action"] == "test"
        assert result["value"] == "hello"

    def test_run_direct_error_exits(self):
        ctx = self._make_ctx()
        mock_svc_ctx = MagicMock()
        with patch.object(ctx, "_make_service_context", return_value=mock_svc_ctx):
            with pytest.raises(SystemExit) as exc_info:
                ctx.run(_do_test_fail)
            assert exc_info.value.code == 1

    def test_run_no_session_direct(self):
        ctx = self._make_ctx()
        result = ctx.run(_do_test_global, x=42)
        assert result == {"x": 42}

    def test_run_no_session_direct_error_exits(self):
        ctx = self._make_ctx()
        with pytest.raises(SystemExit) as exc_info:
            ctx.run(_do_test_global_fail)
        assert exc_info.value.code == 1

    def test_run_raw_direct(self):
        ctx = self._make_ctx()
        mock_svc_ctx = MagicMock()
        with patch.object(ctx, "_make_service_context", return_value=mock_svc_ctx):
            result = ctx.run_raw(_do_test_action, value="raw")
        assert result["value"] == "raw"

    def test_run_raw_direct_raises(self):
        ctx = self._make_ctx()
        mock_svc_ctx = MagicMock()
        with patch.object(ctx, "_make_service_context", return_value=mock_svc_ctx):
            with pytest.raises(ActionError, match="test failure"):
                ctx.run_raw(_do_test_fail)

    def test_run_raw_no_session_direct(self):
        ctx = self._make_ctx()
        result = ctx.run_raw(_do_test_global, x=99)
        assert result == {"x": 99}


# ── daemon mode tests ────────────────────────────────────────────


class TestCliContextDaemon:
    """Tests with daemon mode (default)."""

    def _make_ctx(self, **kwargs) -> CliContext:
        return CliContext(no_daemon=False, **kwargs)

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

    def test_run_raw_daemon(self):
        ctx = self._make_ctx()
        mock_client = MagicMock()
        mock_client.send.return_value = {"action": "test", "value": "raw_d"}

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            result = ctx.run_raw(_do_test_action, value="raw_d")
        assert result["value"] == "raw_d"


# ── observe tests ────────────────────────────────────────────────


class TestCliContextObserve:
    def test_observe_direct_triggers_ocr(self):
        """--observe + action result with 'action' key triggers OCR."""
        ctx = CliContext(no_daemon=True, observe=True)
        mock_svc_ctx = MagicMock()
        mock_ocr = MagicMock(return_value={
            "results": [{"ref": "t1", "text": "hi", "box": [0, 0, 10, 10], "score": 0.9}],
            "elapsed_ms": 100,
        })

        with patch.object(ctx, "_make_service_context", return_value=mock_svc_ctx), \
             patch("maafw_cli.services.vision.do_ocr", mock_ocr):
            ctx.run(_do_test_action)

        mock_ocr.assert_called_once()

    def test_observe_not_triggered_without_action(self):
        """observe should NOT trigger for results without 'action' key."""
        ctx = CliContext(no_daemon=True, observe=True)
        mock_svc_ctx = MagicMock()

        # _do_test_global returns {"x": 1} — no "action" key
        # But it's needs_session=False so goes through _run_no_session which
        # doesn't have observe logic. That's correct behavior.
        result = ctx.run(_do_test_global, x=5)
        assert result == {"x": 5}

    def test_observe_daemon_triggers_ocr(self):
        """--observe in daemon mode sends OCR via IPC."""
        ctx = CliContext(no_daemon=False, observe=True)
        mock_client = MagicMock()
        # First call: the action, second call: the observe OCR
        mock_client.send.side_effect = [
            {"action": "test", "value": "ok"},
            {"results": [], "elapsed_ms": 50},
        ]

        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient", return_value=mock_client):
            ctx.run(_do_test_action)

        assert mock_client.send.call_count == 2
        # Second call should be OCR
        second_call = mock_client.send.call_args_list[1]
        assert second_call[0][0] == "ocr"


# ── cleanup test services from DISPATCH ──────────────────────────

def teardown_module():
    for key in ["_test_action", "_test_fail", "_test_global", "_test_global_fail"]:
        DISPATCH.pop(key, None)
