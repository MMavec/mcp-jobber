"""CLI argument parsing for the `mcp-jobber` entry point."""

from __future__ import annotations

from mcp_jobber.server import _parse_args


def test_defaults_to_stdio():
    args = _parse_args([])
    assert args.http is False
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_http_flag_with_host_and_port():
    args = _parse_args(["--http", "--host", "0.0.0.0", "--port", "9001"])
    assert args.http is True
    assert args.host == "0.0.0.0"
    assert args.port == 9001


def test_port_reads_env(monkeypatch):
    monkeypatch.setenv("PORT", "5050")
    assert _parse_args([]).port == 5050
    monkeypatch.setenv("JOBBER_HTTP_PORT", "6060")
    assert _parse_args([]).port == 6060  # JOBBER_HTTP_PORT wins over PORT
