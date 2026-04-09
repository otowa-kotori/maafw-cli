"""Tests for Custom Recognition & Action support.

Covers:
- core/script_loader.py — importlib loading, class discovery, reload, errors
- services/custom.py — service layer (dispatch, registration logic)
- commands/custom.py — CLI wiring (Click help text)
"""
from __future__ import annotations

import sys
import textwrap
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli
from maafw_cli.core.errors import ActionError
from maafw_cli.services.registry import DISPATCH


runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════
# core/script_loader.py — importlib loading & discovery
# ═══════════════════════════════════════════════════════════════════


class TestScriptLoader:
    """Script loading and class discovery tests."""

    def test_load_recognition_and_action(self, tmp_path):
        """Discover both CustomRecognition and CustomAction subclasses."""
        script = tmp_path / "my_customs.py"
        script.write_text(textwrap.dedent("""\
            from maa.custom_recognition import CustomRecognition
            from maa.custom_action import CustomAction

            class MyReco(CustomRecognition):
                name = "MyReco"
                def analyze(self, context, argv):
                    return None

            class MyAct(CustomAction):
                name = "MyAct"
                def run(self, context, argv):
                    return True
        """))

        from maafw_cli.core.script_loader import load_script

        result = load_script(str(script))
        assert "MyReco" in result.recognitions
        assert "MyAct" in result.actions
        assert len(result.recognitions) == 1
        assert len(result.actions) == 1

    def test_load_recognition_only(self, tmp_path):
        """Script with only recognitions."""
        script = tmp_path / "reco_only.py"
        script.write_text(textwrap.dedent("""\
            from maa.custom_recognition import CustomRecognition

            class FindRed(CustomRecognition):
                name = "FindRed"
                def analyze(self, context, argv):
                    return None
        """))

        from maafw_cli.core.script_loader import load_script

        result = load_script(str(script))
        assert "FindRed" in result.recognitions
        assert len(result.actions) == 0

    def test_load_action_only(self, tmp_path):
        """Script with only actions."""
        script = tmp_path / "action_only.py"
        script.write_text(textwrap.dedent("""\
            from maa.custom_action import CustomAction

            class DoStuff(CustomAction):
                def run(self, context, argv):
                    return True
        """))

        from maafw_cli.core.script_loader import load_script

        result = load_script(str(script))
        assert len(result.recognitions) == 0
        # No `name` attr → falls back to __name__
        assert "DoStuff" in result.actions

    def test_load_empty_script(self, tmp_path):
        """Script with no custom classes — returns empty dicts."""
        script = tmp_path / "empty.py"
        script.write_text("# nothing here\nx = 42\n")

        from maafw_cli.core.script_loader import load_script

        result = load_script(str(script))
        assert len(result.recognitions) == 0
        assert len(result.actions) == 0

    def test_file_not_found(self):
        from maafw_cli.core.script_loader import load_script

        with pytest.raises(FileNotFoundError, match="Script not found"):
            load_script("/nonexistent/path/script.py")

    def test_not_python_file(self, tmp_path):
        script = tmp_path / "data.txt"
        script.write_text("hello")

        from maafw_cli.core.script_loader import load_script

        with pytest.raises(ValueError, match="Not a Python file"):
            load_script(str(script))

    def test_import_error(self, tmp_path):
        """Script with syntax/import errors raises ImportError."""
        script = tmp_path / "bad.py"
        script.write_text("import nonexistent_module_xyz_12345\n")

        from maafw_cli.core.script_loader import load_script

        with pytest.raises(ImportError, match="Failed to import"):
            load_script(str(script))

    def test_reload(self, tmp_path):
        """Reload replaces old module and picks up changes."""
        script = tmp_path / "reloadable.py"
        script.write_text(textwrap.dedent("""\
            from maa.custom_action import CustomAction

            class ActV1(CustomAction):
                name = "MyAct"
                def run(self, context, argv):
                    return True
        """))

        from maafw_cli.core.script_loader import load_script

        r1 = load_script(str(script))
        assert "MyAct" in r1.actions

        # Overwrite with a different class
        script.write_text(textwrap.dedent("""\
            from maa.custom_recognition import CustomRecognition

            class RecoV2(CustomRecognition):
                name = "MyReco"
                def analyze(self, context, argv):
                    return None
        """))

        r2 = load_script(str(script), reload=True)
        assert "MyReco" in r2.recognitions
        assert len(r2.actions) == 0  # old action gone

    def test_name_fallback_to_classname(self, tmp_path):
        """When class has no `name` attribute, use __name__."""
        script = tmp_path / "noname.py"
        script.write_text(textwrap.dedent("""\
            from maa.custom_recognition import CustomRecognition

            class UnnamedReco(CustomRecognition):
                def analyze(self, context, argv):
                    return None
        """))

        from maafw_cli.core.script_loader import load_script

        result = load_script(str(script))
        assert "UnnamedReco" in result.recognitions

    def test_module_naming_unique(self, tmp_path):
        """Different directories with same filename get unique module names."""
        from maafw_cli.core.script_loader import _module_key
        from pathlib import Path

        p1 = tmp_path / "dir1" / "script.py"
        p2 = tmp_path / "dir2" / "script.py"
        p1.parent.mkdir()
        p2.parent.mkdir()
        p1.write_text("")
        p2.write_text("")

        k1 = _module_key(p1)
        k2 = _module_key(p2)
        assert k1 != k2
        assert k1.startswith("maafw_custom_script_")
        assert k2.startswith("maafw_custom_script_")


# ═══════════════════════════════════════════════════════════════════
# services/custom.py — service layer
# ═══════════════════════════════════════════════════════════════════


class TestCustomService:
    """Service-layer tests with mocked session."""

    def test_registered_in_dispatch(self):
        """All custom services should appear in DISPATCH."""
        import maafw_cli.services.custom  # noqa: F401

        for key in ("custom_load", "custom_list", "custom_unload", "custom_clear"):
            assert key in DISPATCH, f"{key} not found in DISPATCH"

    def test_all_need_session(self):
        from maafw_cli.services.custom import (
            do_custom_load, do_custom_list, do_custom_unload, do_custom_clear,
        )
        for fn in (do_custom_load, do_custom_list, do_custom_unload, do_custom_clear):
            assert fn.needs_session is True

    @patch("maafw_cli.core.script_loader.load_script")
    def test_do_custom_load_success(self, mock_load):
        from maafw_cli.core.script_loader import LoadResult
        from maafw_cli.services.custom import do_custom_load

        mock_reco = MagicMock()
        mock_action = MagicMock()
        mock_load.return_value = LoadResult(
            path="/tmp/test.py",
            module_name="maafw_custom_test_abc",
            recognitions={"FindRed": mock_reco},
            actions={"ClickIt": mock_action},
        )

        ctx = MagicMock()
        ctx.session.register_custom_recognition.return_value = True
        ctx.session.register_custom_action.return_value = True

        result = do_custom_load(ctx, path="/tmp/test.py")
        assert result["recognitions"] == ["FindRed"]
        assert result["actions"] == ["ClickIt"]
        ctx.session.register_custom_recognition.assert_called_once_with("FindRed", mock_reco)
        ctx.session.register_custom_action.assert_called_once_with("ClickIt", mock_action)

    @patch("maafw_cli.core.script_loader.load_script")
    def test_do_custom_load_file_not_found(self, mock_load):
        from maafw_cli.services.custom import do_custom_load

        mock_load.side_effect = FileNotFoundError("Script not found: /bad.py")

        ctx = MagicMock()
        with pytest.raises(ActionError, match="Script not found"):
            do_custom_load(ctx, path="/bad.py")

    @patch("maafw_cli.core.script_loader.load_script")
    def test_do_custom_load_import_error(self, mock_load):
        from maafw_cli.services.custom import do_custom_load

        mock_load.side_effect = ImportError("Failed to import")

        ctx = MagicMock()
        with pytest.raises(ActionError, match="Failed to import"):
            do_custom_load(ctx, path="/bad.py")

    @patch("maafw_cli.core.script_loader.load_script")
    def test_do_custom_load_registration_failure(self, mock_load):
        from maafw_cli.core.script_loader import LoadResult
        from maafw_cli.services.custom import do_custom_load

        mock_load.return_value = LoadResult(
            path="/tmp/test.py",
            module_name="maafw_custom_test_abc",
            recognitions={"BadReco": MagicMock()},
            actions={},
        )

        ctx = MagicMock()
        ctx.session.register_custom_recognition.return_value = False

        with pytest.raises(ActionError, match="Failed to register recognition"):
            do_custom_load(ctx, path="/tmp/test.py")

    def test_do_custom_list(self):
        from maafw_cli.services.custom import do_custom_list

        ctx = MagicMock()
        ctx.session.list_custom_recognition.return_value = ["R1", "R2"]
        ctx.session.list_custom_action.return_value = ["A1"]

        result = do_custom_list(ctx)
        assert result["recognitions"] == ["R1", "R2"]
        assert result["actions"] == ["A1"]

    def test_do_custom_unload_recognition(self):
        from maafw_cli.services.custom import do_custom_unload

        ctx = MagicMock()
        ctx.session.unregister_custom_recognition.return_value = True
        ctx.session.unregister_custom_action.return_value = False

        result = do_custom_unload(ctx, name="FindRed", type="recognition")
        assert result["removed_recognition"] is True
        ctx.session.unregister_custom_recognition.assert_called_once_with("FindRed")
        ctx.session.unregister_custom_action.assert_not_called()

    def test_do_custom_unload_action(self):
        from maafw_cli.services.custom import do_custom_unload

        ctx = MagicMock()
        ctx.session.unregister_custom_recognition.return_value = False
        ctx.session.unregister_custom_action.return_value = True

        result = do_custom_unload(ctx, name="ClickIt", type="action")
        assert result["removed_action"] is True
        ctx.session.unregister_custom_recognition.assert_not_called()

    def test_do_custom_unload_both(self):
        from maafw_cli.services.custom import do_custom_unload

        ctx = MagicMock()
        ctx.session.unregister_custom_recognition.return_value = True
        ctx.session.unregister_custom_action.return_value = True

        result = do_custom_unload(ctx, name="Shared", type="both")
        assert result["removed_recognition"] is True
        assert result["removed_action"] is True

    def test_do_custom_unload_not_found(self):
        from maafw_cli.services.custom import do_custom_unload

        ctx = MagicMock()
        ctx.session.unregister_custom_recognition.return_value = False
        ctx.session.unregister_custom_action.return_value = False

        with pytest.raises(ActionError, match="not found"):
            do_custom_unload(ctx, name="NoSuch", type="both")

    def test_do_custom_clear(self):
        from maafw_cli.services.custom import do_custom_clear

        ctx = MagicMock()
        result = do_custom_clear(ctx)
        assert result["cleared"] is True
        ctx.session.clear_custom_recognition.assert_called_once()
        ctx.session.clear_custom_action.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# maafw/action.py — standalone custom action runner
# ═══════════════════════════════════════════════════════════════════


class TestStandaloneCustomActionRunner:
    @patch("maafw_cli.maafw.action.run_pipeline")
    def test_run_custom_action_builds_directhit_temp_pipeline(self, mock_run_pipeline):
        from maafw_cli.maafw.action import (
            _TEMP_CUSTOM_ACTION_ENTRY,
            run_custom_action,
        )

        detail = MagicMock()
        detail.status = MagicMock(succeeded=True)
        detail.nodes = [MagicMock(action=MagicMock(success=True))]
        mock_run_pipeline.return_value = detail

        session = MagicMock()
        ok = run_custom_action(
            session,
            "InputTextCustom",
            custom_action_param={"text": "hello"},
            target_offset=(1, 2, 3, 4),
            box=[10, 20, 30, 40],
            reco_detail='{"ignored": true}',
        )

        assert ok is True
        mock_run_pipeline.assert_called_once()
        call_session, entry, override = mock_run_pipeline.call_args.args
        assert call_session is session
        assert entry == _TEMP_CUSTOM_ACTION_ENTRY
        assert override == {
            _TEMP_CUSTOM_ACTION_ENTRY: {
                "recognition": "DirectHit",
                "roi": [10, 20, 30, 40],
                "action": "Custom",
                "custom_action": "InputTextCustom",
                "custom_action_param": {"text": "hello"},
                "target_offset": [1, 2, 3, 4],
                "next": [],
            }
        }

    @patch("maafw_cli.maafw.action.run_pipeline")
    def test_run_custom_action_omits_optional_fields_when_default(self, mock_run_pipeline):
        from maafw_cli.maafw.action import (
            _TEMP_CUSTOM_ACTION_ENTRY,
            run_custom_action,
        )

        detail = MagicMock()
        detail.status = MagicMock(succeeded=True)
        detail.nodes = [MagicMock(action=MagicMock(success=True))]
        mock_run_pipeline.return_value = detail

        session = MagicMock()
        run_custom_action(session, "ClickTargetCustom")

        override = mock_run_pipeline.call_args.args[2]
        assert override == {
            _TEMP_CUSTOM_ACTION_ENTRY: {
                "recognition": "DirectHit",
                "roi": [0, 0, 0, 0],
                "action": "Custom",
                "custom_action": "ClickTargetCustom",
                "next": [],
            }
        }

    @patch("maafw_cli.maafw.action.run_pipeline")
    def test_run_custom_action_raises_when_pipeline_action_fails(self, mock_run_pipeline):
        from maafw_cli.maafw.action import run_custom_action

        detail = MagicMock()
        detail.status = MagicMock(succeeded=True)
        detail.nodes = [MagicMock(action=MagicMock(success=False))]
        mock_run_pipeline.return_value = detail

        with pytest.raises(ActionError, match="Custom action 'ClickTargetCustom' failed"):
            run_custom_action(MagicMock(), "ClickTargetCustom", box=(1, 2, 3, 4))


# ═══════════════════════════════════════════════════════════════════
# commands/custom.py — CLI wiring
# ═══════════════════════════════════════════════════════════════════


class TestCustomCli:
    """CLI command structure tests using Click's CliRunner."""

    def test_custom_help(self):
        result = runner.invoke(cli, ["custom", "--help"])
        assert result.exit_code == 0
        assert "load" in result.output
        assert "list" in result.output
        assert "unload" in result.output
        assert "clear" in result.output

    def test_custom_load_help(self):
        result = runner.invoke(cli, ["custom", "load", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output
        assert "--reload" in result.output

    def test_custom_list_help(self):
        result = runner.invoke(cli, ["custom", "list", "--help"])
        assert result.exit_code == 0

    def test_custom_unload_help(self):
        result = runner.invoke(cli, ["custom", "unload", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "--type" in result.output
        assert "recognition" in result.output
        assert "action" in result.output
        assert "both" in result.output

    def test_custom_clear_help(self):
        result = runner.invoke(cli, ["custom", "clear", "--help"])
        assert result.exit_code == 0

    def test_action_custom_help(self):
        result = runner.invoke(cli, ["action", "custom", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "--target" in result.output
        assert "--raw" in result.output
