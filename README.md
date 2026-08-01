# 日本珍拾得物センター

全国の警察に届けられた拾得物のうち、思わず事情が気になる物件を
全国共通形式で配信する個人運営サイト。

- 出典: 警察庁「警察国民向けポータルサイト」遺失物公表データ
- 収集: GitHub Actions（毎日JST 06:30、`python -m scraper.run --days 3`）
- 配信: 静的サイト（`site/`）+ JSON

GitHubのクラウド回線から警察庁ポータルへ直接接続するとタイムアウトするため、
日次収集では認証付きのCloudflare Workerを経由する。Workerは1回の呼び出し内で
検索セッション開始から全ページ取得までを完結し、直接実行時は従来どおり
警察庁ポータルへ接続する。

## セットアップ

```sh
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
.venv/bin/python -m scraper.run --days 7
```

日次収集には、GitHubのRepository variable `PORTAL_BASE_URL`とRepository secret
`PORTAL_PROXY_TOKEN`、Cloudflare Worker側の同名secretが必要。

## X自動投稿

```sh
.venv/bin/python -m poster.post --chance 1.0   # 予行演習（投稿しない）
.venv/bin/python -m poster.post --post         # 実投稿（認証情報が必要）
```

有効化には、Xアカウントとdeveloperアプリを作ったうえで、GitHubのRepository secretsに
`X_API_KEY` `X_API_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_SECRET` を登録する
（アプリの権限は Read and write）。未登録のあいだ、ワークフローは予行演習だけを実行する。

投稿する物件は「品名そのもののスコア」で選ぶ。サイト側スコアは在中品も加算するため、
在中品が多いだけのカバン類が上位に来てしまうのを避けている。

## 注意

当サイトは警察庁および都道府県警察とは関係ありません。
物件に心当たりのある方は、各物件記載の問い合わせ先へ直接ご連絡ください。
