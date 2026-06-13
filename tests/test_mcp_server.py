"""Tests for the MCP server's client construction. No network access."""

from __future__ import annotations

import flyan.mcp_server as mcp_server


def _reset_client(monkeypatch):
    """Each test needs a fresh _client so _get_client() actually builds one."""
    monkeypatch.setattr(mcp_server, "_client", None)


def test_get_client_defaults_to_eur(monkeypatch):
    _reset_client(monkeypatch)
    monkeypatch.delenv("FLYAN_CURRENCY", raising=False)

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        mcp_server,
        "RyanAir",
        lambda *, currency: captured.setdefault("currency", currency) or object(),
    )

    mcp_server._get_client()
    assert captured["currency"] == "EUR"


def test_get_client_respects_flyan_currency_env_var(monkeypatch):
    _reset_client(monkeypatch)
    monkeypatch.setenv("FLYAN_CURRENCY", "GBP")

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        mcp_server,
        "RyanAir",
        lambda *, currency: captured.setdefault("currency", currency) or object(),
    )

    mcp_server._get_client()
    assert captured["currency"] == "GBP"
