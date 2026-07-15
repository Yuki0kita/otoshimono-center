import pathlib

import pytest

from scraper.client import PortalClient

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_proxy_token_header_is_added(monkeypatch):
    monkeypatch.setenv("PORTAL_PROXY_TOKEN", "test-token")

    client = PortalClient(interval_sec=0)

    headers = {name.lower(): value for name, value in client._opener.addheaders}
    assert headers["x-otoshimono-proxy-token"] == "test-token"


def test_proxy_token_header_is_omitted_by_default(monkeypatch):
    monkeypatch.delenv("PORTAL_PROXY_TOKEN", raising=False)

    client = PortalClient(interval_sec=0)

    assert all(
        name.lower() != "x-otoshimono-proxy-token"
        for name, _ in client._opener.addheaders
    )


def test_batch_proxy_returns_over_limit(monkeypatch):
    monkeypatch.setenv("PORTAL_PROXY_TOKEN", "test-token")
    client = PortalClient(interval_sec=0)
    captured = {}

    def fake_request(url, payload):
        captured.update(url=url, payload=payload)
        return {
            "first": (FIXTURES / "search_over_limit.html").read_text(),
            "pages": [],
        }

    monkeypatch.setattr(client, "_request_json", fake_request)
    page = client.search_all_pages(["30"], "3200", "2026/07/14", "2026/07/15")

    assert page.over_limit
    assert captured["url"].endswith("/batch-search")
    assert captured["payload"]["pref_codes"] == ["30"]


def test_batch_proxy_rejects_incomplete_pages(monkeypatch):
    monkeypatch.setenv("PORTAL_PROXY_TOKEN", "test-token")
    client = PortalClient(interval_sec=0)
    monkeypatch.setattr(
        client,
        "_request_json",
        lambda *_: {
            "first": (FIXTURES / "search_result_tokyo_wallet.html").read_text(),
            "pages": [],
        },
    )

    with pytest.raises(RuntimeError, match="expected=250 actual=0"):
        client.search_all_pages(["30"], "1600", "2026/07/01", "2026/07/02")
