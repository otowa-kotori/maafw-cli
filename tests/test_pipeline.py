"""Tests for the pipeline module — Phase 4.

Covers:
- maafw/pipeline.py  — low-level wrappers (mocked Resource/Tasker)
- services/pipeline.py — service layer (dispatch, needs_session, logic)
- core/output.py — format_pipeline_table
- commands/pipeline.py — CLI wiring (Click help text)
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli
from maafw_cli.core.errors import ActionError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.registry import DISPATCH


runner = CliRunner()


# ── helpers ──────────────────────────────────────────────────────

def _make_node_detail(name="TestNode", completed=True,
                      algo="TemplateMatch", hit=True, box=(10, 20, 30, 40),
                      score=0.95, text=None,
                      action_type="Click", action_success=True):
    """Build a fake NodeDetail-like object."""
    best_result = SimpleNamespace(score=score, text=text)
    recognition = SimpleNamespace(
        algorithm=algo, hit=hit, box=box, best_result=best_result,
    )
    action = SimpleNamespace(action=action_type, success=action_success)
    return SimpleNamespace(
        name=name, completed=completed,
        recognition=recognition, action=action,
    )


def _make_task_detail(nodes=None, status=None):
    """Build a fake TaskDetail-like object."""
    if status is None:
        from maa.define import Status
        status = Status(3000) if nodes else Status(4000)  # succeeded / failed
    return SimpleNamespace(nodes=nodes or [], status=status)


# ═══════════════════════════════════════════════════════════════════
# maafw/pipeline.py — low-level wrappers
# ═══════════════════════════════════════════════════════════════════


class TestPipelineMaafw:
    """Low-level pipeline functions with mocked Session."""

    def _make_session(self):
        return MagicMock()

    def test_load_pipeline_success(self):
        from maafw_cli.maafw.pipeline import load_pipeline

        session = self._make_session()
        session.load_pipeline.return_value = True

        assert load_pipeline(session, "/tmp/pipeline") is True
        session.load_pipeline.assert_called_once_with("/tmp/pipeline")

    def test_load_pipeline_failure(self):
        from maafw_cli.maafw.pipeline import load_pipeline

        session = self._make_session()
        session.load_pipeline.return_value = False

        assert load_pipeline(session, "/tmp/pipeline") is False

    def test_load_pipeline_no_resource(self):
        from maafw_cli.maafw.pipeline import load_pipeline

        session = self._make_session()
        session.load_pipeline.side_effect = ActionError("Resource initialization failed.")

        with pytest.raises(ActionError, match="Resource initialization failed"):
            load_pipeline(session, "/tmp/pipeline")

    def test_run_pipeline_success(self):
        from maafw_cli.maafw.pipeline import run_pipeline

        detail = _make_task_detail([_make_node_detail()])
        session = self._make_session()
        tasker = MagicMock()
        tasker.post_task.return_value.wait.return_value.get.return_value = detail
        session.get_tasker.return_value = tasker

        result = run_pipeline(session, "StartNode", {"A": {}})

        tasker.post_task.assert_called_once_with("StartNode", {"A": {}})
        assert result is detail

    def test_run_pipeline_no_tasker(self):
        from maafw_cli.maafw.pipeline import run_pipeline

        session = self._make_session()
        session.get_tasker.return_value = None

        with pytest.raises(ActionError, match="Failed to initialize tasker"):
            run_pipeline(session, "StartNode")

    def test_run_pipeline_no_result(self):
        from maafw_cli.maafw.pipeline import run_pipeline

        session = self._make_session()
        tasker = MagicMock()
        tasker.post_task.return_value.wait.return_value.get.return_value = None
        session.get_tasker.return_value = tasker

        with pytest.raises(ActionError, match="returned no result"):
            run_pipeline(session, "StartNode")

    def test_list_nodes(self):
        from maafw_cli.maafw.pipeline import list_nodes

        session = self._make_session()
        session.list_nodes.return_value = ["A", "B", "C"]

        assert list_nodes(session) == ["A", "B", "C"]

    def test_list_nodes_no_resource(self):
        from maafw_cli.maafw.pipeline import list_nodes

        session = self._make_session()
        session.list_nodes.side_effect = ActionError("Resource not initialized.")

        with pytest.raises(ActionError, match="Resource not initialized"):
            list_nodes(session)

    def test_get_node_data(self):
        from maafw_cli.maafw.pipeline import get_node_data

        session = self._make_session()
        session.get_node_data.return_value = {"action": "Click"}

        assert get_node_data(session, "NodeA") == {"action": "Click"}

    def test_get_node_data_no_resource(self):
        from maafw_cli.maafw.pipeline import get_node_data

        session = self._make_session()
        session.get_node_data.return_value = None
        assert get_node_data(session, "NodeA") is None


# ═══════════════════════════════════════════════════════════════════
# services/pipeline.py — service layer
# ═══════════════════════════════════════════════════════════════════


class TestPipelineService:
    """Service-layer tests."""

    def test_registered_in_dispatch(self):
        """All pipeline services should appear in DISPATCH."""
        # Force import to trigger registration
        import maafw_cli.services.pipeline  # noqa: F401

        for key in ("pipeline_run", "pipeline_load", "pipeline_list",
                     "pipeline_show", "pipeline_validate"):
            assert key in DISPATCH, f"{key} not found in DISPATCH"

    def test_run_needs_session(self):
        from maafw_cli.services.pipeline import do_pipeline_run
        assert do_pipeline_run.needs_session is True

    def test_load_needs_session(self):
        from maafw_cli.services.pipeline import do_pipeline_load
        assert do_pipeline_load.needs_session is True

    def test_list_needs_session(self):
        from maafw_cli.services.pipeline import do_pipeline_list
        assert do_pipeline_list.needs_session is True

    def test_show_needs_session(self):
        from maafw_cli.services.pipeline import do_pipeline_show
        assert do_pipeline_show.needs_session is True

    def test_validate_needs_session(self):
        from maafw_cli.services.pipeline import do_pipeline_validate
        assert do_pipeline_validate.needs_session is True

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode", "EndNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_basic(self, mock_load, mock_list, mock_run, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_run

        detail = _make_task_detail([_make_node_detail("StartNode")])
        mock_run.return_value = detail

        ctx = MagicMock()
        ctx.session_name = "test"
        result = do_pipeline_run(ctx, path="/tmp/p", entry="StartNode")

        assert result["entry"] == "StartNode"
        assert result["session"] == "test"
        assert result["status"] == "succeeded"
        assert result["node_count"] == 1
        assert result["nodes"][0]["name"] == "StartNode"
        assert result["nodes"][0]["completed"] is True

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode", "EndNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_default_entry(self, mock_load, mock_list, mock_run, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_run

        detail = _make_task_detail([_make_node_detail("StartNode")])
        mock_run.return_value = detail

        ctx = MagicMock()
        ctx.session_name = None
        result = do_pipeline_run(ctx, path="/tmp/p")  # no entry

        assert result["entry"] == "StartNode"  # defaults to first node
        mock_run.assert_called_once()

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_with_override(self, mock_load, mock_list, mock_run, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_run

        detail = _make_task_detail([_make_node_detail()])
        mock_run.return_value = detail

        ctx = MagicMock()
        ctx.session_name = None
        override_json = '{"StartNode": {"timeout": 5000}}'
        do_pipeline_run(ctx, path="/tmp/p", entry="StartNode", override=override_json)

        args, kwargs = mock_run.call_args
        # run_pipeline(controller, entry, override_dict) — positional
        assert args[2] == {"StartNode": {"timeout": 5000}}

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_invalid_override(self, mock_load, mock_list, mock_run, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_run

        ctx = MagicMock()
        with pytest.raises(ActionError, match="Invalid override JSON"):
            do_pipeline_run(ctx, path="/tmp/p", entry="StartNode", override="{bad json}")

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_failed_status(self, mock_load, mock_list, mock_run, mock_init):
        """Pipeline with nodes but failed status should report 'failed'."""
        from maa.define import Status
        from maafw_cli.services.pipeline import do_pipeline_run

        detail = _make_task_detail(
            [_make_node_detail("StartNode")],
            status=Status(4000),  # failed
        )
        mock_run.return_value = detail

        ctx = MagicMock()
        ctx.session_name = "test"
        result = do_pipeline_run(ctx, path="/tmp/p", entry="StartNode")
        assert result["status"] == "failed"

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.run_pipeline")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["StartNode"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_run_succeeded_no_nodes(self, mock_load, mock_list, mock_run, mock_init):
        """Pipeline with no nodes but succeeded status should report 'succeeded'."""
        from maa.define import Status
        from maafw_cli.services.pipeline import do_pipeline_run

        detail = _make_task_detail([], status=Status(3000))  # succeeded
        mock_run.return_value = detail

        ctx = MagicMock()
        ctx.session_name = "test"
        result = do_pipeline_run(ctx, path="/tmp/p", entry="StartNode")
        assert result["status"] == "succeeded"
        assert result["node_count"] == 0

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["A", "B"])
    @patch("maafw_cli.maafw.pipeline.load_pipeline", return_value=True)
    def test_do_pipeline_load(self, mock_load, mock_list, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_load

        ctx = MagicMock()
        result = do_pipeline_load(ctx, path="/tmp/p")
        assert result["loaded"] is True
        assert result["nodes"] == ["A", "B"]
        assert result["node_count"] == 2

    @patch("maafw_cli.maafw.pipeline.list_nodes", return_value=["X", "Y", "Z"])
    def test_do_pipeline_list(self, mock_list):
        from maafw_cli.services.pipeline import do_pipeline_list

        ctx = MagicMock()
        result = do_pipeline_list(ctx)
        assert result["nodes"] == ["X", "Y", "Z"]
        assert result["node_count"] == 3

    @patch("maafw_cli.maafw.pipeline.get_node_data", return_value={"action": "Click"})
    def test_do_pipeline_show(self, mock_get):
        from maafw_cli.services.pipeline import do_pipeline_show

        ctx = MagicMock()
        result = do_pipeline_show(ctx, node="NodeA")
        assert result["node"] == "NodeA"
        assert result["definition"] == {"action": "Click"}

    @patch("maafw_cli.maafw.pipeline.get_node_data", return_value=None)
    def test_do_pipeline_show_not_found(self, mock_get):
        from maafw_cli.services.pipeline import do_pipeline_show

        ctx = MagicMock()
        with pytest.raises(ActionError, match="Node not found"):
            do_pipeline_show(ctx, node="Missing")

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.validate_pipeline")
    def test_do_pipeline_validate_valid(self, mock_val, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_validate

        mock_val.return_value = {"valid": True, "nodes": ["A"], "node_count": 1}
        ctx = MagicMock()
        result = do_pipeline_validate(ctx, path="/tmp/p")
        assert result["valid"] is True

    @patch("maafw_cli.services.pipeline.init_toolkit")
    @patch("maafw_cli.maafw.pipeline.validate_pipeline")
    def test_do_pipeline_validate_invalid(self, mock_val, mock_init):
        from maafw_cli.services.pipeline import do_pipeline_validate

        mock_val.return_value = {"valid": False, "error": "bad json", "nodes": [], "node_count": 0}
        ctx = MagicMock()
        result = do_pipeline_validate(ctx, path="/tmp/p")
        assert result["valid"] is False
        assert "bad json" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# core/output.py — format_pipeline_table
# ═══════════════════════════════════════════════════════════════════


class TestPipelineOutput:
    """Output formatting tests."""

    def _sample_result(self):
        return {
            "session": "default",
            "entry": "StartNode",
            "status": "succeeded",
            "nodes": [
                {
                    "name": "ClickLogin",
                    "completed": True,
                    "recognition": {"algorithm": "TemplateMatch", "hit": True, "box": [120, 45, 80, 24], "score": 0.95},
                    "action": {"type": "Click", "success": True},
                },
                {
                    "name": "WaitHome",
                    "completed": True,
                    "recognition": {"algorithm": "OCR", "hit": True, "text": "\u9996\u9875"},
                    "action": {"type": "DoNothing", "success": True},
                },
                {
                    "name": "Done",
                    "completed": True,
                    "recognition": {"algorithm": "DirectHit", "hit": True},
                    "action": {"type": "StopTask", "success": True},
                },
            ],
            "node_count": 3,
            "elapsed_ms": 2500,
        }

    def test_format_summary(self):
        result = self._sample_result()
        output = OutputFormatter.format_pipeline_table(result, verbose=False)
        assert "Pipeline: StartNode" in output
        assert "default" in output
        assert "succeeded" in output
        assert "3 nodes" in output
        assert "2500ms" in output
        # Summary should NOT contain individual node names
        assert "ClickLogin" not in output

    def test_format_verbose(self):
        result = self._sample_result()
        output = OutputFormatter.format_pipeline_table(result, verbose=True)
        assert "Pipeline: StartNode" in output
        assert "ClickLogin" in output
        assert "WaitHome" in output
        assert "Done" in output
        assert "\u2713" in output  # checkmark for completed
        assert "TemplateMatch hit" in output
        assert "\u2192 Click" in output
        assert "\u2192 StopTask" in output
        assert "succeeded" in output

    def test_format_verbose_with_text(self):
        result = self._sample_result()
        output = OutputFormatter.format_pipeline_table(result, verbose=True)
        assert '\u9996\u9875' in output  # OCR text "首页"

    def test_format_empty_nodes(self):
        result = {
            "session": "default", "entry": "X", "status": "no_nodes",
            "nodes": [], "node_count": 0, "elapsed_ms": 100,
        }
        output = OutputFormatter.format_pipeline_table(result, verbose=True)
        assert "0 nodes" in output
        # No separator lines when no nodes
        assert "\u2500" not in output

    def test_format_failed_node(self):
        result = {
            "session": "default", "entry": "X", "status": "succeeded",
            "nodes": [
                {
                    "name": "FailNode",
                    "completed": False,
                    "recognition": {"algorithm": "TemplateMatch", "hit": False},
                    "action": {"type": "Click", "success": False},
                },
            ],
            "node_count": 1, "elapsed_ms": 500,
        }
        output = OutputFormatter.format_pipeline_table(result, verbose=True)
        assert "\u2717" in output  # cross mark for not completed
        assert "TemplateMatch miss" in output


# ═══════════════════════════════════════════════════════════════════
# commands/pipeline.py — CLI wiring
# ═══════════════════════════════════════════════════════════════════


class TestPipelineCli:
    """CLI command structure tests using Click's CliRunner."""

    def test_pipeline_help(self):
        result = runner.invoke(cli, ["pipeline", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "load" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "validate" in result.output

    def test_pipeline_run_help(self):
        result = runner.invoke(cli, ["pipeline", "run", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output
        assert "ENTRY" in result.output
        assert "--override" in result.output

    def test_pipeline_load_help(self):
        result = runner.invoke(cli, ["pipeline", "load", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output

    def test_pipeline_list_help(self):
        result = runner.invoke(cli, ["pipeline", "list", "--help"])
        assert result.exit_code == 0

    def test_pipeline_show_help(self):
        result = runner.invoke(cli, ["pipeline", "show", "--help"])
        assert result.exit_code == 0
        assert "NODE" in result.output

    def test_pipeline_validate_help(self):
        result = runner.invoke(cli, ["pipeline", "validate", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output


# ═══════════════════════════════════════════════════════════════════
# _summarize_node helper
# ═══════════════════════════════════════════════════════════════════


class TestSummarizeNode:
    """Test the _summarize_node helper."""

    def test_full_node(self):
        from maafw_cli.services.pipeline import _summarize_node

        nd = _make_node_detail(
            name="A", completed=True,
            algo="TemplateMatch", hit=True, box=(1, 2, 3, 4),
            score=0.9, text=None,
            action_type="Click", action_success=True,
        )
        summary = _summarize_node(nd)
        assert summary["name"] == "A"
        assert summary["completed"] is True
        assert summary["recognition"]["algorithm"] == "TemplateMatch"
        assert summary["recognition"]["hit"] is True
        assert summary["recognition"]["box"] == [1, 2, 3, 4]
        assert summary["recognition"]["score"] == 0.9
        assert "text" not in summary["recognition"]
        assert summary["action"]["type"] == "Click"
        assert summary["action"]["success"] is True

    def test_node_with_text(self):
        from maafw_cli.services.pipeline import _summarize_node

        nd = _make_node_detail(name="B", text="Hello")
        summary = _summarize_node(nd)
        assert summary["recognition"]["text"] == "Hello"

    def test_node_no_recognition(self):
        from maafw_cli.services.pipeline import _summarize_node

        nd = SimpleNamespace(name="C", completed=True, recognition=None, action=None)
        summary = _summarize_node(nd)
        assert summary["name"] == "C"
        assert "recognition" not in summary
        assert "action" not in summary
