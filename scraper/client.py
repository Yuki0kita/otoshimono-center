"""警察国民向けポータルの検索クライアント（標準ライブラリのみ）。

セッション確立 → メニュー選択 → 検索POST → ページングGET の順で
人がブラウザで操作するのと同じフローをたどる。
リクエストごとに REQUEST_INTERVAL_SEC 待機して負荷をかけない。
"""

from __future__ import annotations

import http.cookiejar
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .constants import BASE_URL, PAGE_SIZE, REQUEST_INTERVAL_SEC
from .parse import FoundItem, SearchPage, parse_search_page

logger = logging.getLogger(__name__)

_USER_AGENT = "otoshimono-center/0.1 (personal aggregator; polite crawl)"
_REQUEST_TIMEOUT_SEC = 30
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SEC = 5


class PortalClient:
    def __init__(self, interval_sec: float = REQUEST_INTERVAL_SEC) -> None:
        self._interval = interval_sec
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        headers = [("User-Agent", _USER_AGENT)]
        proxy_token = os.environ.get("PORTAL_PROXY_TOKEN")
        if proxy_token:
            headers.append(("X-Otoshimono-Proxy-Token", proxy_token))
        self._opener.addheaders = headers
        self._batch_proxy = bool(proxy_token)
        self._session_ready = False

    def _open(
        self,
        request: str | urllib.request.Request,
        timeout_sec: int = _REQUEST_TIMEOUT_SEC,
    ) -> str:
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            time.sleep(self._interval)
            try:
                with self._opener.open(request, timeout=timeout_sec) as res:
                    return res.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == _RETRY_ATTEMPTS:
                    raise
                logger.warning(
                    "request failed (%d/%d), retrying in %ss: %s",
                    attempt,
                    _RETRY_ATTEMPTS,
                    _RETRY_BACKOFF_SEC,
                    exc,
                )
                time.sleep(_RETRY_BACKOFF_SEC)
        raise AssertionError("unreachable")

    def _request(self, url: str, data: dict[str, list[str] | str] | None = None) -> str:
        body = None
        if data is not None:
            pairs: list[tuple[str, str]] = []
            for key, value in data.items():
                if isinstance(value, list):
                    pairs.extend((key, v) for v in value)
                else:
                    pairs.append((key, value))
            body = urllib.parse.urlencode(pairs).encode()
        request = urllib.request.Request(url, data=body)
        return self._open(request)

    def _request_json(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        return json.loads(self._open(request, timeout_sec=120))

    def _ensure_session(self) -> None:
        if self._session_ready:
            return
        self._request(f"{BASE_URL}/SZDSA0101")
        self._request(
            f"{BASE_URL}/SZDSA0101/next",
            {
                "menuSelect": "1",
                "menuSelectValue": "",
                "langCd": "01",
                "commonHeaderZoomSize": "100",
            },
        )
        self._session_ready = True

    def search(
        self,
        pref_codes: list[str],
        bunrui_code: str,
        date_from: str,
        date_to: str,
    ) -> SearchPage:
        """検索を実行し1ページ目を返す。日付は YYYY/MM/DD 形式。"""
        self._ensure_session()
        html = self._request(
            f"{BASE_URL}/SZDWA0101/search",
            {
                "ishitsuFromDate": date_from,
                "ishitsuToDate": date_to,
                "initIshitsuToDate": date_to,
                "prefValue": pref_codes,
                "_prefValue": "1",
                "prefCheck": pref_codes[0] if pref_codes else "",
                "_cityCdValue": "1",
                "fushoFlg": "true",
                "_fushoFlg": "on",
                "bashoShuruiValue": "",
                "shisetsuNm": "",
                "searchMethod": "1",
                "bunruiValue": bunrui_code,
                "goodsTypeValue": "",
                "buppinNmValue": "",
                "keyword": "",
                "keywordEdit": "",
                "conditionFlg": "1",
                "sortNum": "",
                "sortType": "",
                "pageTopRecordNum": "0",
                "dispCountPerPageSelect": "10,20,100",
                "limitNum": "500",
                "langCd": "01",
                "initFushoFlg": "true",
                "initSearchMethod": "1",
                "initConditionFlg": "1",
                "totalRecordCount": "0",
                "commonHeaderZoomSize": "100",
            },
        )
        return parse_search_page(html)

    def fetch_page(self, top_record_num: int) -> SearchPage:
        """直前の検索結果をページングで取得する（サーバー側セッションに依存）。"""
        html = self._request(
            f"{BASE_URL}/SZDWA0101"
            f"?&gDispCountPerPage={PAGE_SIZE}&gPageTopRecordNum={top_record_num}"
            "&OC_TRANSACTION_TOKEN=null"
        )
        return parse_search_page(html)

    def search_all_pages(
        self,
        pref_codes: list[str],
        bunrui_code: str,
        date_from: str,
        date_to: str,
    ) -> SearchPage:
        """検索して全ページ分の物件を集める。500件超なら over_limit で返す。"""
        if self._batch_proxy:
            return self._search_all_pages_via_proxy(
                pref_codes, bunrui_code, date_from, date_to
            )

        first = self.search(pref_codes, bunrui_code, date_from, date_to)
        if first.over_limit or first.total <= len(first.items):
            return first

        items: list[FoundItem] = []
        seen: set[str] = set()
        for top in range(0, first.total, PAGE_SIZE):
            page = self.fetch_page(top)
            if page.over_limit:
                return page
            for item in page.items:
                if item.item_id not in seen:
                    seen.add(item.item_id)
                    items.append(item)
        logger.info(
            "search bunrui=%s prefs=%d total=%d fetched=%d",
            bunrui_code, len(pref_codes), first.total, len(items),
        )
        return SearchPage(total=first.total, items=items, over_limit=False)

    def _search_all_pages_via_proxy(
        self,
        pref_codes: list[str],
        bunrui_code: str,
        date_from: str,
        date_to: str,
    ) -> SearchPage:
        payload = self._request_json(
            f"{BASE_URL}/batch-search",
            {
                "pref_codes": pref_codes,
                "bunrui_code": bunrui_code,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
        first = parse_search_page(payload["first"])
        if first.over_limit or first.total <= len(first.items):
            return first

        items: list[FoundItem] = []
        seen: set[str] = set()
        for html in payload.get("pages", []):
            page = parse_search_page(html)
            for item in page.items:
                if item.item_id not in seen:
                    seen.add(item.item_id)
                    items.append(item)
        if len(items) < first.total:
            raise RuntimeError(
                f"proxy returned incomplete result: expected={first.total} actual={len(items)}"
            )
        logger.info(
            "proxy search bunrui=%s prefs=%d total=%d fetched=%d",
            bunrui_code, len(pref_codes), first.total, len(items),
        )
        return SearchPage(total=first.total, items=items, over_limit=False)
