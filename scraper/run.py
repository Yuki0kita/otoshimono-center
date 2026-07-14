"""収集の実行エントリポイント。

使い方:
    python3 -m scraper.run --days 3          # 直近3日分を収集してマージ
    python3 -m scraper.run --days 14         # 初回バックフィル

500件超で結果が返らない検索は、都道府県リストの二分割 → 日付範囲の
二分割の順で自動的に条件を狭めて再検索する。
結果は data/items.json（蓄積）と site/data/items.json（配信用）へ書き出す。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import pathlib

from .client import PortalClient
from .constants import PREF_CODES, TARGET_BUNRUI, BUNRUI_CODES
from .parse import FoundItem
from .score import score_item

logger = logging.getLogger(__name__)

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "items.json"
SITE_DATA_PATH = ROOT / "site" / "data" / "items.json"

# 配信用に保持する最大件数（3ヶ月で公表が消えるため十分な余裕）
MAX_ITEMS = 5000


def _collect(
    client: PortalClient,
    prefs: list[str],
    bunrui: str,
    date_from: dt.date,
    date_to: dt.date,
) -> list[FoundItem]:
    """500件超なら都道府県→日付の順で二分割しながら全件回収する。"""
    page = client.search_all_pages(
        prefs, bunrui, date_from.strftime("%Y/%m/%d"), date_to.strftime("%Y/%m/%d")
    )
    if not page.over_limit:
        return page.items

    if len(prefs) > 1:
        mid = len(prefs) // 2
        return _collect(client, prefs[:mid], bunrui, date_from, date_to) + _collect(
            client, prefs[mid:], bunrui, date_from, date_to
        )
    if date_from < date_to:
        mid_date = date_from + (date_to - date_from) // 2
        return _collect(client, prefs, bunrui, date_from, mid_date) + _collect(
            client, prefs, bunrui, mid_date + dt.timedelta(days=1), date_to
        )
    logger.warning(
        "1県1日でも500件超のため取得を断念: pref=%s bunrui=%s date=%s",
        prefs, bunrui, date_from,
    )
    return []


def _to_record(item: FoundItem, bunrui: str) -> dict:
    pref_code = item.storage_pref_code
    return {
        "id": item.item_id,
        "found_date": item.found_date,
        "expiry_date": item.expiry_date,
        "pref": PREF_CODES.get(pref_code or "", ""),
        "city": item.city,
        "place": item.place,
        "name": item.name,
        "features": item.features,
        "contents": item.contents,
        "contact": item.contact,
        "ref_no": item.ref_no,
        "category": BUNRUI_CODES[bunrui],
        "score": score_item(item),
    }


def _load_existing() -> dict[str, dict]:
    if not DATA_PATH.exists():
        return {}
    payload = json.loads(DATA_PATH.read_text())
    return {rec["id"]: rec for rec in payload.get("items", [])}


def _sort_key(rec: dict) -> tuple:
    # 拾得日降順（不明は最後）、同日ならスコア降順
    date = rec["found_date"] if rec["found_date"] != "不明" else "0000/00/00"
    return (date, rec["score"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3, help="遡って収集する日数")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    today = dt.date.today()
    date_from = today - dt.timedelta(days=args.days)
    client = PortalClient()
    all_prefs = list(PREF_CODES)

    records = _load_existing()
    fetched = 0
    for bunrui in TARGET_BUNRUI:
        items = _collect(client, all_prefs, bunrui, date_from, today)
        fetched += len(items)
        for item in items:
            records[item.item_id] = _to_record(item, bunrui)
        logger.info("bunrui=%s(%s): %d件", bunrui, BUNRUI_CODES[bunrui], len(items))

    ordered = sorted(records.values(), key=_sort_key, reverse=True)[:MAX_ITEMS]
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "警察庁 警察国民向けポータルサイト（遺失物公表データ）",
        "prefs": list(PREF_CODES.values()),  # 北から南の表示順
        "items": ordered,
    }
    for path in (DATA_PATH, SITE_DATA_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    logger.info("取得%d件 / 蓄積%d件 を書き出しました", fetched, len(ordered))


if __name__ == "__main__":
    main()
