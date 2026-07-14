import pathlib

from scraper.parse import FoundItem, _split_date_cell, parse_search_page

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParseSearchPage:
    def test_normal_result(self):
        page = parse_search_page(_load("search_result_tokyo_wallet.html"))
        assert not page.over_limit
        assert page.total == 250
        assert len(page.items) == 10
        first = page.items[0]
        assert first.found_date == "2026/07/01"
        assert first.expiry_date == "2026/10/02"
        assert first.name == "小銭入れ（チャック式）"
        assert first.features == "黒色"
        assert first.contact == "厚別警察署 011-896-0110"
        assert first.ref_no == "10-130-26-001840-0014"

    def test_over_limit(self):
        page = parse_search_page(_load("search_over_limit.html"))
        assert page.over_limit
        assert page.items == []

    def test_zero_result(self):
        page = parse_search_page(_load("search_zero_result.html"))
        assert not page.over_limit
        assert page.total == 0
        assert page.items == []

    def test_empty_html(self):
        page = parse_search_page("")
        assert not page.over_limit
        assert page.total == 0
        assert page.items == []


class TestFoundItem:
    def _item(self, **kwargs) -> FoundItem:
        defaults = dict(
            found_date="2026/07/01", expiry_date="2026/10/02", city="東京都千代田区",
            place="路上／歩道上", name="木彫りの熊", features="茶色", contents="",
            contact="麹町警察署 03-0000-0110", ref_no="30-101-26-000001-0001",
        )
        defaults.update(kwargs)
        return FoundItem(**defaults)

    def test_storage_pref_from_ref_no(self):
        assert self._item().storage_pref_code == "30"

    def test_facility_ref_no_has_no_pref(self):
        # JR等の施設保管は数字のみの採番で都道府県コードを持たない
        assert self._item(ref_no="8462456").storage_pref_code is None

    def test_item_id_combines_contact_and_ref(self):
        item = self._item()
        assert item.item_id == "麹町警察署 03-0000-0110|30-101-26-000001-0001"


class TestSplitDateCell:
    def test_date_with_expiry(self):
        assert _split_date_cell("2026/07/01 (2026/10/02)") == ("2026/07/01", "2026/10/02")

    def test_unknown_date(self):
        assert _split_date_cell("不明") == ("不明", "")

    def test_date_without_expiry(self):
        assert _split_date_cell("2026/07/01") == ("2026/07/01", "")
