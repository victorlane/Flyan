from __future__ import annotations

import sys
from unittest.mock import Mock


def test_import_transport_makes_no_http_requests(monkeypatch):
    """flyan.transport import must not trigger network calls."""
    mock_client = Mock()
    mock_async_client = Mock()
    monkeypatch.setattr("httpx.Client", mock_client)
    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    sys.modules.pop("flyan.transport", None)

    import flyan.transport  # noqa: F401  -- imported for its import-time side effects

    mock_client.assert_not_called()
    mock_async_client.assert_not_called()
