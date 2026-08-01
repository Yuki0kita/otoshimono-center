"""X（旧Twitter）API v2 への投稿クライアント（標準ライブラリのみ）。

POST /2/tweets を OAuth 1.0a User Context で署名して呼ぶ。
認証情報は環境変数から読む。値はログに出さない。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

TWEET_ENDPOINT = "https://api.x.com/2/tweets"
_REQUEST_TIMEOUT_SEC = 30

# X の文字数計算: 全角（CJK等）は2、半角は1。URLは長さに関わらず一律23
TWEET_WEIGHT_LIMIT = 280
URL_WEIGHTED_LEN = 23

_REQUIRED_ENV = (
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_SECRET",
)


class MissingCredentials(Exception):
    """必要な環境変数が揃っていない。"""


class PostFailed(Exception):
    """X API がエラーを返した。"""


def _weighted_char_len(char: str) -> int:
    """1文字の重み。X の Twitter-text 仕様に準拠した簡易版。"""
    code = ord(char)
    # 半角扱いの範囲（ASCII、記号、半角カナ手前まで）
    if code <= 0x10FF or 0x2000 <= code <= 0x200D or 0x2010 <= code <= 0x201F or 0x2032 <= code <= 0x2037:
        return 1
    return 2


def weighted_length(text: str) -> int:
    """投稿文の重み付き文字数。URLは実長でなく23として数える。"""
    total = 0
    for token in text.split():
        if token.startswith(("http://", "https://")):
            total += URL_WEIGHTED_LEN
            # 空白ぶんは下の走査で数えないため、ここでは本文から除外して扱う
            text = text.replace(token, "", 1)
    for char in text:
        total += _weighted_char_len(char)
    return total


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(str(value), safe="~")


def _build_oauth_header(
    method: str, url: str, credentials: dict[str, str]
) -> str:
    """OAuth 1.0a の Authorization ヘッダーを組み立てる。

    JSON ボディの POST では、署名対象に本文を含めない（oauth_パラメータのみ）。
    """
    oauth_params = {
        "oauth_consumer_key": credentials["X_API_KEY"],
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": credentials["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    param_string = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join(
        [method.upper(), _percent_encode(url), _percent_encode(param_string)]
    )
    signing_key = (
        f"{_percent_encode(credentials['X_API_SECRET'])}"
        f"&{_percent_encode(credentials['X_ACCESS_SECRET'])}"
    )
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode(), base_string.encode(), hashlib.sha1
        ).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature
    return "OAuth " + ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )


def load_credentials(env: dict[str, str] | None = None) -> dict[str, str]:
    """環境変数から認証情報を読む。欠けていれば MissingCredentials。"""
    source = env if env is not None else os.environ
    missing = [name for name in _REQUIRED_ENV if not source.get(name)]
    if missing:
        raise MissingCredentials(", ".join(missing))
    return {name: source[name] for name in _REQUIRED_ENV}


def post_tweet(text: str, credentials: dict[str, str]) -> str:
    """ツイートを投稿し、投稿IDを返す。"""
    body = json.dumps({"text": text}).encode()
    request = urllib.request.Request(
        TWEET_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": _build_oauth_header("POST", TWEET_ENDPOINT, credentials),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SEC) as res:
            payload = json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PostFailed(f"HTTP {exc.code}: {detail}") from exc
    return payload.get("data", {}).get("id", "")
