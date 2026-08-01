"""投稿する拾得物の選定と、投稿文の組み立て。

掲載内容は警察が公表している事実のみを扱う。落とし主や拾得者を
詮索する表現は入れない（サイト本体と同じ編集方針）。
"""

from __future__ import annotations

import random

from scraper.parse import FoundItem
from scraper.score import score_item

from .x_client import TWEET_WEIGHT_LIMIT, weighted_length

SITE_URL = "https://otoshimono-center.pages.dev/"

# 投稿対象にする最低スコア（サイト側の「注目の拾得物」と同じ基準）
MIN_SCORE = 40
# 在中品を並べる最大数
MAX_CONTENTS = 3

# 冒頭のフック。毎回同じだと機械的に見えるため複数から選ぶ
_HOOKS = (
    "【本日の珍拾得物】",
    "【全国から届いた落とし物】",
    "【こんな物が警察に届いています】",
    "【今日の落とし物】",
)


def _format_date(ymd: str) -> str:
    parts = ymd.split("/")
    if len(parts) != 3:
        return ymd
    _, month, day = parts
    return f"{int(month)}月{int(day)}日"


def describe(item: dict) -> str:
    """1件ぶんの説明文（官製の乾いた文体）を組み立てる。"""
    when = (
        "拾得日不明"
        if item.get("found_date") in ("", "不明")
        else f"{_format_date(item['found_date'])}ごろ"
    )
    # 市区町村は都道府県名を含む（例: 東京都千代田区）ため重ねない
    area = item.get("city") if item.get("city") not in ("", "不詳") else item.get("pref", "")
    place = item.get("place", "")
    spot = place if place and place != "不明／その他" else ""
    where = "の".join(p for p in (area, spot) if p) or "場所不詳"

    text = f"{when}、{where}で「{item['name']}」が拾われました。"
    if item.get("features"):
        text += f"特徴は{item['features']}。"
    contents = [c for c in item.get("contents", "").split("、") if c]
    if contents:
        listed = "、".join(contents[:MAX_CONTENTS])
        rest = f"ほか{len(contents) - MAX_CONTENTS}点" if len(contents) > MAX_CONTENTS else ""
        text += f"あわせて{listed}{rest}が確認されています。"
    return text


def compose(item: dict, rng: random.Random | None = None) -> str:
    """1件ぶんの投稿文を組み立てる。"""
    chooser = rng or random
    body = describe(item)
    lines = [chooser.choice(_HOOKS), "", body, "", f"問い合わせ: {item['contact']}", SITE_URL]
    text = "\n".join(lines)

    # 長すぎる場合は在中品リストを落として詰める
    if weighted_length(text) > TWEET_WEIGHT_LIMIT:
        trimmed = dict(item)
        trimmed["contents"] = ""
        lines[2] = describe(trimmed)
        text = "\n".join(lines)
    while weighted_length(text) > TWEET_WEIGHT_LIMIT and len(lines[2]) > 20:
        lines[2] = lines[2][:-10] + "…"
        text = "\n".join(lines)
    return text


def name_score(item: dict) -> int:
    """品名だけで測ったスコア。

    サイト側のスコアは在中品も加算するため、在中品が多いだけのカバン類が
    上位に来る。投稿では「品名そのものが珍しい」ものを選ぶ。
    """
    return score_item(
        FoundItem(
            found_date="", expiry_date="", city="", place="",
            name=item.get("name", ""), features="", contents="",
            contact="", ref_no="",
        )
    )


def select_candidates(items: list[dict], posted_ids: set[str]) -> list[dict]:
    """投稿候補を、優先度の高い順に並べて返す。

    条件: 未投稿・品名スコアが基準以上。品名スコアが高く、拾得日が新しいものを優先する。
    """
    candidates = [
        item
        for item in items
        if item["id"] not in posted_ids and name_score(item) >= MIN_SCORE
    ]

    def found_date(item: dict) -> str:
        value = item.get("found_date", "")
        return value if value and value != "不明" else "0000/00/00"

    # 安定ソートを重ねる: 拾得日の新しい順 → 品名スコアの高い順（スコアが優先）
    by_date = sorted(candidates, key=found_date, reverse=True)
    return sorted(by_date, key=name_score, reverse=True)
