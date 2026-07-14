"""検索結果ページ（SZDWA0101）のHTMLパース。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 「250件中1-10件を表示しています。」
_COUNT_RE = re.compile(r"(\d+)件中(\d+)-(\d+)件を表示")
_OVER_LIMIT_TEXT = "500件を超えているため"
# 問い合わせ番号の先頭2桁は保管都道府県コード（例: 10-130-26-001840-0014）
_REF_PREF_RE = re.compile(r"^(\d{2})-\d{3}-")


@dataclass
class FoundItem:
    found_date: str  # 拾われた日付（"不明" あり）
    expiry_date: str  # 保管満期日（"" あり）
    city: str  # 遺失場所の市区町村（"不詳" あり）
    place: str  # 場所の種類または施設名
    name: str  # 拾われた物
    features: str  # 特徴（色など）
    contents: str  # その他の物品など（在中品）
    contact: str  # 問い合わせ先
    ref_no: str  # 問い合わせ番号

    @property
    def item_id(self) -> str:
        """問い合わせ先＋番号で一意化する（番号は保管者ごとの採番のため）。"""
        return f"{self.contact}|{self.ref_no}"

    @property
    def storage_pref_code(self) -> str | None:
        """問い合わせ番号から保管都道府県コードを推定する。施設保管は None。"""
        m = _REF_PREF_RE.match(self.ref_no)
        return m.group(1) if m else None


@dataclass
class SearchPage:
    total: int
    items: list[FoundItem]
    over_limit: bool


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def parse_search_page(html: str) -> SearchPage:
    """検索結果HTMLから件数と物件一覧を取り出す。

    件数表示がない場合は0件ページとして扱う（500件超エラーは over_limit で区別）。
    """
    if _OVER_LIMIT_TEXT in html:
        return SearchPage(total=-1, items=[], over_limit=True)

    m = _COUNT_RE.search(html)
    total = int(m.group(1)) if m else 0

    items: list[FoundItem] = []
    idx = html.find('id="table-pc"')
    if idx < 0:
        return SearchPage(total=total, items=items, over_limit=False)

    tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html[idx:], re.S)
    if not tbody_m:
        return SearchPage(total=total, items=items, over_limit=False)

    for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S):
        cells = [
            _strip_tags(c)
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_m.group(1), re.S)
        ]
        if len(cells) != 8:
            continue  # ヘッダー行や構造変更行はスキップ
        date_cell, city, place, name, features, contents, contact, ref_no = cells
        found_date, expiry_date = _split_date_cell(date_cell)
        items.append(
            FoundItem(
                found_date=found_date,
                expiry_date=expiry_date,
                city=city,
                place=place,
                name=name,
                features=features,
                contents=contents,
                contact=contact,
                ref_no=ref_no,
            )
        )
    return SearchPage(total=total, items=items, over_limit=False)


def _split_date_cell(cell: str) -> tuple[str, str]:
    """「2026/07/01 (2026/10/02)」→ (拾得日, 保管満期日)。「不明」はそのまま返す。"""
    m = re.match(r"([\d/]+|不明)\s*(?:\(([\d/]+)\))?", cell)
    if not m:
        return cell, ""
    return m.group(1), m.group(2) or ""
