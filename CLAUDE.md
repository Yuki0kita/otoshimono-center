# 日本珍拾得物センター

警察庁「警察国民向けポータルサイト」の遺失物公表データを収集し、
珍品度スコア付きの静的フィードとして配信する個人サービス。
本家「日本不審者情報センター」（散在する公式発表を標準化して配信）のフォーマットを
拾得物に転用したもの。

## 構成

- `scraper/` — 標準ライブラリのみのスクレイパー（依存ゼロ）
  - `client.py` — セッション確立→検索POST→ページングGET。1.5秒待機で礼儀正しく巡回
  - `parse.py` — 検索結果テーブルのパース（500件超エラーの検出を含む）
  - `score.py` — キーワードルールの珍品度スコア。閾値は `FEATURED_THRESHOLD`
  - `run.py` — エントリポイント。500件超は「都道府県二分割→日付二分割」で自動リトライ
- `site/` — 静的サイト（Vanilla JS）。`site/data/items.json` を読むだけ
- `data/items.json` — 蓄積データ（idはcontact|ref_no）
- `.github/workflows/scrape.yml` — 毎日JST 06:30に収集してコミット

## 開発

- テスト: `.venv/bin/python -m pytest tests/`（fixturesは実レスポンスHTML）
- 収集: `.venv/bin/python -m scraper.run --days 3`（ローカルPythonは3.9なので `from __future__ import annotations` 必須）
- プレビュー: launch.json の `otoshimono-center`（ポート8646）

## ドメイン知識

- ポータルの検索は「種類（bunruiValue）」必須、1検索500件上限（超えると0件+エラー文言）
- 問い合わせ番号 `XX-YYY-...` の先頭2桁は保管都道府県コード（constants.PREF_CODES）。
  数字のみの番号はJR等の施設保管で都道府県不明
- 拾得日「不明」の物件が存在する（遺失日ベースの登録）
- 公表は拾得日からおおむね3ヶ月で消える。MAX_ITEMS=5000で古いものから破棄

## 運用ルール

- 収集対象カテゴリは `constants.TARGET_BUNRUI`。増やすときはリクエスト数（=巡回時間）に注意
- 出典表記と「警察とは無関係の個人サイト」の免責は消さない
- 掲載は公表データそのまま。個人が特定される情報は元データ側で除外済みだが、
  万一含まれていた場合は即削除する
