from scraper.client import PortalClient


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
