"""Tests for daemon JSON-line protocol."""
from __future__ import annotations

import pytest

from maafw_cli.daemon.protocol import (
    decode,
    encode,
    error_response,
    make_request,
    ok_response,
)


class TestEncodeDecode:
    """Round-trip and edge-case tests for encode/decode."""

    def test_round_trip_simple(self):
        msg = {"id": "abc", "action": "click", "session": None, "params": {"target": "e2"}}
        raw = encode(msg)
        assert raw.endswith(b"\n")
        assert decode(raw) == msg

    def test_round_trip_chinese(self):
        msg = {"id": "x1", "text": "你好世界", "emoji": "🎮"}
        assert decode(encode(msg)) == msg

    def test_round_trip_special_chars(self):
        msg = {"id": "s1", "text": 'line1\nline2\ttab\\back"quote'}
        assert decode(encode(msg)) == msg

    def test_round_trip_empty_dict(self):
        msg: dict = {}
        assert decode(encode(msg)) == msg

    def test_round_trip_nested(self):
        msg = {"id": "n1", "data": {"nested": {"deep": [1, 2, 3]}}}
        assert decode(encode(msg)) == msg


class TestDecodeErrors:
    """Malformed input handling."""

    def test_empty_bytes(self):
        with pytest.raises(ValueError, match="Empty line"):
            decode(b"")

    def test_empty_whitespace(self):
        with pytest.raises(ValueError, match="Empty line"):
            decode(b"   \n")

    def test_malformed_json(self):
        with pytest.raises(ValueError, match="Malformed JSON"):
            decode(b"{bad json}\n")

    def test_not_a_dict(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            decode(b"[1,2,3]\n")

    def test_plain_string(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            decode(b'"hello"\n')

    def test_plain_number(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            decode(b"42\n")


class TestRequestHelpers:
    def test_make_request_defaults(self):
        req = make_request("click", {"target": "e1"})
        assert req["action"] == "click"
        assert req["params"] == {"target": "e1"}
        assert req["session"] is None
        assert isinstance(req["id"], str)
        assert len(req["id"]) == 12

    def test_make_request_with_session(self):
        req = make_request("ocr", session="phone", request_id="custom-id")
        assert req["session"] == "phone"
        assert req["id"] == "custom-id"
        assert req["params"] == {}


class TestResponseHelpers:
    def test_ok_response(self):
        resp = ok_response("r1", {"count": 5})
        assert resp == {"id": "r1", "ok": True, "data": {"count": 5}}

    def test_ok_response_empty_data(self):
        resp = ok_response("r2")
        assert resp == {"id": "r2", "ok": True, "data": {}}

    def test_error_response(self):
        resp = error_response("r3", "not found", exit_code=3)
        assert resp == {"id": "r3", "ok": False, "error": "not found", "exit_code": 3}

    def test_error_response_default_exit_code(self):
        resp = error_response("r4", "fail")
        assert resp["exit_code"] == 1


class TestMultiLineHandling:
    """Ensure protocol handles line boundaries correctly."""

    def test_decode_strips_trailing_newline(self):
        raw = b'{"id":"1"}\n'
        assert decode(raw) == {"id": "1"}

    def test_decode_strips_crlf(self):
        raw = b'{"id":"1"}\r\n'
        assert decode(raw) == {"id": "1"}

    def test_encode_always_ends_with_newline(self):
        raw = encode({"id": "1"})
        assert raw.endswith(b"\n")
        assert raw.count(b"\n") == 1
