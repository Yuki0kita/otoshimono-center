from scraper.parse import FoundItem
from scraper.score import FEATURED_THRESHOLD, score_item


def _item(name="", features="", contents="") -> FoundItem:
    return FoundItem(
        found_date="2026/07/01", expiry_date="2026/10/02", city="不詳",
        place="路上／歩道上", name=name, features=features, contents=contents,
        contact="テスト警察署 00-0000-0110", ref_no="30-101-26-000001-0001",
    )


class TestScoreItem:
    def test_rare_item_exceeds_threshold(self):
        assert score_item(_item(name="入れ歯")) >= FEATURED_THRESHOLD

    def test_wood_carving_bear(self):
        assert score_item(_item(name="木彫りの熊", features="茶色")) >= FEATURED_THRESHOLD

    def test_boring_item_scores_zero(self):
        assert score_item(_item(name="傘", features="黒色")) == 0

    def test_score_never_negative(self):
        assert score_item(_item(name="傘 財布 ハンカチ")) == 0

    def test_contents_also_scored(self):
        # 在中品に生き物がいるケース
        assert score_item(_item(name="段ボール箱", contents="カメ")) >= FEATURED_THRESHOLD

    def test_empty_item(self):
        assert score_item(_item()) == 0

    def test_keywords_accumulate(self):
        single = score_item(_item(name="ぬいぐるみ"))
        combo = score_item(_item(name="ぬいぐるみ", contents="手編みの人形"))
        assert combo > single
