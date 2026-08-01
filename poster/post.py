"""X への自動投稿エントリポイント。

使い方:
    python3 -m poster.post                 # 予行演習（投稿文を表示するだけ）
    python3 -m poster.post --post          # 実際に投稿する（認証情報が必要）

「不定期」な見え方にするため、実行のたびに --chance の確率で投稿を見送り、
かつ前回投稿から --min-interval-hours 未満なら必ず見送る。
投稿済みIDは data/posted.json に記録し、同じ質問を二度投稿しない。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import pathlib
import random

from .compose import compose, select_candidates
from .x_client import (
    MissingCredentials,
    load_credentials,
    post_tweet,
    weighted_length,
)

logger = logging.getLogger(__name__)

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "site" / "data" / "items.json"
POSTED_PATH = ROOT / "data" / "posted.json"


def _load_posted() -> dict:
    if not POSTED_PATH.exists():
        return {"last_posted_at": "", "posts": []}
    return json.loads(POSTED_PATH.read_text())


def _save_posted(state: dict) -> None:
    POSTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSTED_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def _hours_since(timestamp: str) -> float:
    if not timestamp:
        return float("inf")
    last = dt.datetime.fromisoformat(timestamp)
    return (dt.datetime.now(dt.timezone.utc) - last).total_seconds() / 3600


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true", help="実際に投稿する")
    parser.add_argument(
        "--chance", type=float, default=0.5,
        help="この実行で投稿する確率（不定期に見せるため）",
    )
    parser.add_argument(
        "--min-interval-hours", type=float, default=8.0,
        help="前回投稿からこの時間が経つまで投稿しない",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    state = _load_posted()
    elapsed = _hours_since(state.get("last_posted_at", ""))
    if elapsed < args.min_interval_hours:
        logger.info(
            "前回投稿から%.1f時間（下限%.1f時間）のため見送ります",
            elapsed, args.min_interval_hours,
        )
        return
    if random.random() > args.chance:
        logger.info("今回は投稿を見送ります（確率 %.2f）", args.chance)
        return

    items = json.loads(ITEMS_PATH.read_text())["items"]
    posted_ids = {post["id"] for post in state["posts"]}
    candidates = select_candidates(items, posted_ids)
    if not candidates:
        logger.info("未投稿の候補がありません")
        return

    item = candidates[0]
    text = compose(item)
    logger.info("投稿文（%d/280）:\n%s", weighted_length(text), text)

    if not args.post:
        logger.info("予行演習のため投稿しません（--post で実行）")
        return

    try:
        credentials = load_credentials()
    except MissingCredentials as exc:
        logger.error("認証情報が未設定です: %s", exc)
        raise SystemExit(1) from exc

    tweet_id = post_tweet(text, credentials)
    state["posts"].append(
        {
            "id": item["id"],
            "tweet_id": tweet_id,
            "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
    )
    state["last_posted_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    _save_posted(state)
    logger.info("投稿しました: %s", tweet_id)


if __name__ == "__main__":
    main()
