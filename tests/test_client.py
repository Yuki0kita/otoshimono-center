import io
import pathlib
import urllib.error

import pytest

from scraper.client import PortalClient
from scraper.parse import parse_search_page

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


def test_batch_proxy_counts_received_rows_before_deduplication(monkeypatch):
    monkeypatch.setenv("PORTAL_PROXY_TOKEN", "test-token")
    client = PortalClient(interval_sec=0)
    fixture = (FIXTURES / "search_result_tokyo_wallet.html").read_text()
    monkeypatch.setattr(
        client,
        "_request_json",
        lambda *_: {"first": fixture, "pages": [fixture] * 25},
    )

    page = client.search_all_pages(["30"], "1600", "2026/07/01", "2026/07/02")

    assert page.total == 250
    assert len(page.items) == 10


def _direct_client(monkeypatch) -> PortalClient:
    monkeypatch.delenv("PORTAL_PROXY_TOKEN", raising=False)
    return PortalClient(interval_sec=0)


def test_direct_paging_rejects_incomplete_pages(monkeypatch):
    client = _direct_client(monkeypatch)
    fixture = (FIXTURES / "search_result_tokyo_wallet.html").read_text()
    zero = (FIXTURES / "search_zero_result.html").read_text()
    monkeypatch.setattr(client, "search", lambda *_: parse_search_page(fixture))
    # 2ページ目以降でセッションが切れ、件数表示のない0件ページが返る想定
    pages = iter([fixture] + [zero] * 24)
    monkeypatch.setattr(client, "fetch_page", lambda _top: parse_search_page(next(pages)))

    with pytest.raises(RuntimeError, match="expected=250 actual=10"):
        client.search_all_pages(["30"], "1600", "2026/07/01", "2026/07/02")


def test_open_retries_then_raises(monkeypatch):
    client = _direct_client(monkeypatch)
    monkeypatch.setattr("scraper.client._RETRY_BACKOFF_SEC", 0)
    calls = []

    def failing_open(request, timeout):
        calls.append(request)
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(client._opener, "open", failing_open)

    with pytest.raises(urllib.error.URLError):
        client._request("https://example.invalid/")
    assert len(calls) == 3


def test_open_recovers_after_transient_failure(monkeypatch):
    client = _direct_client(monkeypatch)
    monkeypatch.setattr("scraper.client._RETRY_BACKOFF_SEC", 0)
    attempts = iter([urllib.error.URLError("reset"), io.BytesIO("ok".encode())])

    def flaky_open(request, timeout):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(client._opener, "open", flaky_open)

    assert client._request("https://example.invalid/") == "ok"
