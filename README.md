# 日本珍拾得物センター

全国の警察に届けられた拾得物のうち、思わず事情が気になる物件を
全国共通形式で配信する個人運営サイト。

- 出典: 警察庁「警察国民向けポータルサイト」遺失物公表データ
- 収集: GitHub Actions（毎日JST 06:30、`python -m scraper.run --days 3`）
- 配信: 静的サイト（`site/`）+ JSON

## セットアップ

```sh
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
.venv/bin/python -m scraper.run --days 7
```

## 注意

当サイトは警察庁および都道府県警察とは関係ありません。
物件に心当たりのある方は、各物件記載の問い合わせ先へ直接ご連絡ください。
