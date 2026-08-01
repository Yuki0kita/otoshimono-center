import pytest

from poster.compose import compose, describe, select_candidates
from poster.x_client import (
    MissingCredentials,
    TWEET_WEIGHT_LIMIT,
    load_credentials,
    weighted_length,
)


def _item(**kwargs) -> dict:
    base = {
        "id": "a|1", "found_date": "2026/07/13", "expiry_date": "2026/10/13",
        "pref": "静岡県", "city": "静岡県駿東郡長泉町", "place": "路上／歩道上",
        "name": "インコ", "features": "白色、水色、青色", "contents": "",
        "contact": "裾野警察署 055-995-0110", "ref_no": "49-100-26-000640-0001",
        "category": "動植物類", "score": 50,
    }
    base.update(kwargs)
    return base


class TestWeightedLength:
    def test_japanese_counts_two_each(self):
        assert weighted_length("拾得") == 4

    def test_url_counts_as_23(self):
        assert weighted_length("https://example.com/very/long/path") == 23


class TestDescribe:
    def test_basic_sentence(self):
        text = describe(_item())
        assert "7月13日ごろ" in text
        assert "静岡県駿東郡長泉町の路上／歩道上" in text
        assert "「インコ」が拾われました" in text
        assert "特徴は白色、水色、青色。" in text

    def test_unknown_date(self):
        assert describe(_item(found_date="不明")).startswith("拾得日不明")

    def test_unknown_city_falls_back_to_pref(self):
        assert "静岡県で" in describe(_item(city="不詳", place="不明／その他"))

    def test_contents_are_capped(self):
        text = describe(_item(contents="A、B、C、D、E"))
        assert "ほか2点" in text

    def test_no_features_omits_clause(self):
        assert "特徴は" not in describe(_item(features=""))


class TestCompose:
    def test_within_tweet_limit(self):
        assert weighted_length(compose(_item())) <= TWEET_WEIGHT_LIMIT

    def test_long_contents_still_within_limit(self):
        text = compose(_item(contents="、".join(["長い品名の在中品"] * 40)))
        assert weighted_length(text) <= TWEET_WEIGHT_LIMIT

    def test_long_name_still_within_limit(self):
        assert weighted_length(compose(_item(name="あ" * 200))) <= TWEET_WEIGHT_LIMIT

    def test_includes_site_url_and_contact(self):
        text = compose(_item())
        assert "otoshimono-center.pages.dev" in text
        assert "裾野警察署" in text


class TestSelectCandidates:
    def test_excludes_already_posted(self):
        items = [_item(id="a"), _item(id="b")]
        assert [i["id"] for i in select_candidates(items, {"a"})] == ["b"]

    def test_excludes_boring_name(self):
        assert select_candidates([_item(name="傘", score=90)], set()) == []

    def test_excludes_bag_that_scored_only_via_contents(self):
        # 在中品が多いだけのカバンはサイト側スコアが高くても投稿しない
        bag = _item(name="手提げかばん", contents="猫、犬、インコ", score=120)
        assert select_candidates([bag], set()) == []

    def test_higher_name_score_first(self):
        items = [_item(id="low", name="ぬいぐるみ"), _item(id="high", name="入れ歯")]
        assert select_candidates(items, set())[0]["id"] == "high"

    def test_newer_date_first_within_same_score(self):
        items = [
            _item(id="old", found_date="2026/07/01"),
            _item(id="new", found_date="2026/07/13"),
        ]
        assert select_candidates(items, set())[0]["id"] == "new"

    def test_empty_input(self):
        assert select_candidates([], set()) == []


class TestLoadCredentials:
    def test_raises_when_missing(self):
        with pytest.raises(MissingCredentials):
            load_credentials({"X_API_KEY": "only-one"})
