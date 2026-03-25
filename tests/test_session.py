"""Tests for session save/load round-trip and SessionInfo.from_dict tolerance."""
from __future__ import annotations

import json

from maafw_cli.core.session import SessionInfo, save_session, load_session


class TestSessionRoundTrip:
    def test_adb_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.session.get_data_dir", lambda: tmp_path)
        info = SessionInfo(
            type="adb", device="emu-5554", adb_path="/usr/bin/adb",
            address="127.0.0.1:5554", screencap_methods=3, input_methods=7,
            config={"key": "val"}, screenshot_short_side=1080,
            name="phone",
        )
        save_session(info)
        loaded = load_session()
        assert loaded is not None
        assert loaded.type == "adb"
        assert loaded.device == "emu-5554"
        assert loaded.address == "127.0.0.1:5554"
        assert loaded.screenshot_short_side == 1080
        assert loaded.name == "phone"

    def test_win32_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.session.get_data_dir", lambda: tmp_path)
        info = SessionInfo(
            type="win32", device="Notepad", address="0x1234",
            screencap_methods=2, input_methods=4, window_name="Notepad",
        )
        save_session(info)
        loaded = load_session()
        assert loaded is not None
        assert loaded.type == "win32"
        assert loaded.window_name == "Notepad"
        assert loaded.address == "0x1234"

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.session.get_data_dir", lambda: tmp_path)
        assert load_session() is None

    def test_load_corrupt_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.session.get_data_dir", lambda: tmp_path)
        (tmp_path / "session.json").write_text("{not valid", encoding="utf-8")
        assert load_session() is None


class TestSessionInfoFromDict:
    """from_dict tolerates extra and missing fields."""

    def test_extra_fields_ignored(self):
        d = {
            "type": "adb", "device": "emu",
            "extra_key": "should_not_crash",
            "another": 42,
        }
        info = SessionInfo.from_dict(d)
        assert info.type == "adb"
        assert info.device == "emu"

    def test_missing_optional_fields_use_defaults(self):
        d = {"type": "win32", "device": "Notepad"}
        info = SessionInfo.from_dict(d)
        assert info.type == "win32"
        assert info.adb_path == ""
        assert info.screenshot_short_side == 720
