#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests
from dateutil import parser as date_parser

JST = timezone(timedelta(hours=9))
LOOKBACK_HOURS = 30
TIMEOUT_SECONDS = 45
USER_AGENT = "Inoreader-GitHub-Briefing/1.0 (+GitHub Actions)"

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs"
OUTPUT_JSON = OUTPUT_DIR / "latest.json"
OUTPUT_HTML = OUTPUT_DIR / "latest.html"
STATUS_JSON = OUTPUT_DIR / "status.json"

FEEDS = [
    {
        "folder": "00_毎日確認",
        "priority": 1,
        "rss": "https://www.inoreader.com/stream/user/1004825287/tag/00_%E6%AF%8E%E6%97%A5%E7%A2%BA%E8%AA%8D",
        "json": "https://www.inoreader.com/stream/user/1004825287/tag/00_%E6%AF%8E%E6%97%A5%E7%A2%BA%E8%AA%8D/view/json",
    },
    {
        "folder": "06_左派ニュース・社会主義戦略",
        "priority": 2,
        "rss": "https://www.inoreader.com/stream/user/1004825287/tag/06_%E5%B7%A6%E6%B4%BE%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9%E3%83%BB%E7%A4%BE%E4%B8%BB%E7%BE%A9%E6%88%A6%E7%95%A5",
        "json": "https://www.inoreader.com/stream/user/1004825287/tag/06_%E5%B7%A6%E6%B4%BE%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9%E3%83%BB%E7%A4%BE%E4%B8%BB%E7%BE%A9%E6%88%A6%E7%95%A5/view/json",
    },
]

TRACKING_QUERY_KEYS = {
    "fbclid", "gclid", "mc_cid", "mc_eid",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}


@dataclass
class Article:
    id: str
    title: str
    url: str
    author: str
    source: str
    published_at: str | None
    content: str
    source_folders: list[str]
    priority: int
    date_missing: bool = False


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_html(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: str) -> str:
    value = clean_html(value).casefold()
    value = re.sub(r"""[\s\-–—_「」『』【】〈〉《》"'“”‘’!?！？。、，,:：;；・]+""", "", value)
    return value


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        query = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.casefold() not in TRACKING_QUERY_KEYS
        ]
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme, parts.netloc.casefold(), path, urlencode(query), ""))
    except ValueError:
        return value


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = date_parser.parse(str(value))
    except (ValueError, TypeError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def first_nonempty(mapping: Any, keys: list[str]) -> Any:
    for key in keys:
        if isinstance(mapping, dict) and mapping.get(key) not in (None, ""):
            return mapping[key]
        try:
            value = getattr(mapping, key)
            if value not in (None, ""):
                return value
        except (AttributeError, TypeError):
            pass
    return ""


def fetch_url(url: str) -> requests.Response:
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT_SECONDS,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/150.0.0.0 Safari/537.36"
                    ),
                    "Accept": (
                        "application/rss+xml, application/atom+xml, "
                        "application/json, text/xml, application/xml, */*"
                    ),
                },
            )
            response.raise_for_status()

            if not response.content:
                raise ValueError("Empty response")

            return response

        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    assert last_error is not None
    raise last_error


def rss_entries(response: requests.Response) -> tuple[str, list[dict[str, Any]]]:
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    text = response.content.decode(encoding, errors="replace")

    # BOM、先頭の空白、XMLで使用できない制御文字を除去
    text = text.lstrip("\ufeff \t\r\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    parsed = feedparser.parse(text)

    if getattr(parsed, "bozo", False) and not parsed.entries:
        content_type = response.headers.get("content-type", "")
        prefix = text[:300].replace("\n", "\\n")

        raise ValueError(
            f"RSS parse error: {parsed.bozo_exception}; "
            f"status={response.status_code}; "
            f"content_type={content_type}; "
            f"length={len(response.content)}; "
            f"body_prefix={prefix!r}"
        )
    title = clean_html(first_nonempty(parsed.feed, ["title"])) or "Inoreader output feed"
    entries: list[dict[str, Any]] = []
    for entry in parsed.entries:
        source_data = first_nonempty(entry, ["source"])
        if isinstance(source_data, dict):
            source_title = clean_html(source_data.get("title", ""))
        else:
            source_title = ""
        entries.append({
            "id": first_nonempty(entry, ["id", "guid"]),
            "title": first_nonempty(entry, ["title"]),
            "url": first_nonempty(entry, ["link"]),
            "author": first_nonempty(entry, ["author", "creator"]),
            "source": source_title,
            "published": first_nonempty(entry, ["published", "updated", "created"]),
            "content": first_nonempty(entry, ["content", "summary", "description"]),
        })
    return title, entries


def json_entries(response: requests.Response) -> tuple[str, list[dict[str, Any]]]:
    data = response.json()
    title = clean_html(data.get("title", "")) or "Inoreader JSON feed"
    raw_items = data.get("items", [])
    entries: list[dict[str, Any]] = []
    for item in raw_items:
        canonical = item.get("canonical") or []
        url = ""
        if canonical and isinstance(canonical[0], dict):
            url = canonical[0].get("href", "")
        summary = item.get("summary") or {}
        origin = item.get("origin") or {}
        entries.append({
            "id": item.get("id", ""),
            "title": item.get("title", ""),
            "url": url,
            "author": item.get("author", ""),
            "source": origin.get("title", ""),
            "published": item.get("published") or item.get("updated"),
            "content": summary.get("content", ""),
        })
    return title, entries


def build_article(entry: dict[str, Any], folder: str, priority: int) -> Article:
    title = clean_html(entry.get("title")) or "(タイトルなし)"
    url = normalize_url(clean_html(entry.get("url")))
    author = clean_html(entry.get("author"))
    source = clean_html(entry.get("source"))
    content_value = entry.get("content", "")
    if isinstance(content_value, list):
        content_value = " ".join(
            str(x.get("value", "")) if isinstance(x, dict) else str(x)
            for x in content_value
        )
    content = clean_html(content_value)
    dt = parse_datetime(entry.get("published"))
    raw_id = clean_html(entry.get("id")) or url or f"{title}|{folder}"
    article_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24]
    return Article(
        id=article_id,
        title=title,
        url=url,
        author=author,
        source=source,
        published_at=dt.isoformat() if dt else None,
        content=content,
        source_folders=[folder],
        priority=priority,
        date_missing=dt is None,
    )


def fetch_feed(feed: dict[str, Any]) -> tuple[list[Article], dict[str, Any]]:
    errors: list[str] = []
    for feed_type in ("rss", "json"):
        url = feed[feed_type]
        try:
            response = fetch_url(url)
            if feed_type == "rss":
                feed_title, entries = rss_entries(response)
            else:
                feed_title, entries = json_entries(response)
            articles = [
                build_article(entry, feed["folder"], feed["priority"])
                for entry in entries
            ]
            return articles, {
                "folder": feed["folder"],
                "success": True,
                "format": feed_type,
                "url": url,
                "feed_title": feed_title,
                "http_status": response.status_code,
                "item_count": len(articles),
                "errors_before_success": errors,
            }
        except Exception as exc:  # Report both RSS and JSON failures.
            errors.append(f"{feed_type}: {type(exc).__name__}: {exc}")
    return [], {
        "folder": feed["folder"],
        "success": False,
        "format": None,
        "url": None,
        "feed_title": None,
        "http_status": None,
        "item_count": 0,
        "errors": errors,
    }


def deduplicate(articles: list[Article]) -> list[Article]:
    by_key: dict[str, Article] = {}
    for article in articles:
        key = article.url or normalize_title(article.title) or article.id
        current = by_key.get(key)
        if current is None:
            by_key[key] = article
            continue
        merged_folders = sorted(set(current.source_folders + article.source_folders))
        preferred = article if article.priority < current.priority else current
        preferred.source_folders = merged_folders
        preferred.priority = min(article.priority, current.priority)
        if not preferred.content:
            preferred.content = current.content or article.content
        by_key[key] = preferred
    return sorted(
        by_key.values(),
        key=lambda a: (
            a.priority,
            -(parse_datetime(a.published_at).timestamp() if a.published_at else 0),
        ),
    )


def render_html(payload: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    status_rows = []
    for status in payload["feed_status"]:
        state = "成功" if status["success"] else "失敗"
        details = (
            f'{esc(status.get("format"))}／{status.get("item_count", 0)}件'
            if status["success"]
            else esc("; ".join(status.get("errors", [])))
        )
        status_rows.append(
            f"<tr><td>{esc(status['folder'])}</td><td>{state}</td><td>{details}</td></tr>"
        )

    article_sections = []
    for article in payload["articles"]:
        folders = " / ".join(article["source_folders"])
        published = article["published_at"] or "日時不明"
        url = article["url"]
        title_html = (
            f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(article["title"])}</a>'
            if url else esc(article["title"])
        )
        content = article["content"] or "フィード本文・概要なし"
        article_sections.append(f"""
<article>
  <h2>{title_html}</h2>
  <p class="meta">フォルダ: {esc(folders)} ／ 媒体: {esc(article["source"] or "不明")} ／ 著者: {esc(article["author"] or "不明")} ／ 公開日時: {esc(published)}</p>
  <p>{esc(content)}</p>
</article>
""")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inoreader 朝刊用データ</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans JP",sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.7;color:#222}}
h1{{font-size:1.8rem}} h2{{font-size:1.2rem;margin-bottom:.2rem}}
article{{border-top:1px solid #ddd;padding:1rem 0}}
.meta{{font-size:.86rem;color:#555}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}} td,th{{border:1px solid #ccc;padding:.5rem;text-align:left}}
code{{background:#f3f3f3;padding:.1rem .25rem}}
</style>
</head>
<body>
<h1>Inoreader 朝刊用データ</h1>
<p>更新日時: {esc(payload["generated_at_jst"])} ／ 対象期間: 直近{payload["lookback_hours"]}時間 ／ 記事数: {payload["article_count"]}</p>
<p><a href="latest.json">機械可読JSON</a></p>
<h2>取得状況</h2>
<table><thead><tr><th>フォルダ</th><th>状態</th><th>詳細</th></tr></thead><tbody>
{''.join(status_rows)}
</tbody></table>
<section>
{''.join(article_sections) if article_sections else "<p>対象記事はありません。</p>"}
</section>
</body>
</html>
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = now_utc()
    threshold = generated - timedelta(hours=LOOKBACK_HOURS)

    all_articles: list[Article] = []
    feed_status: list[dict[str, Any]] = []

    for feed in FEEDS:
        articles, status = fetch_feed(feed)
        all_articles.extend(articles)
        feed_status.append(status)

    recent: list[Article] = []
    for article in all_articles:
        if article.published_at is None:
            recent.append(article)
            continue
        dt = parse_datetime(article.published_at)
        if dt and dt >= threshold:
            recent.append(article)

    deduped = deduplicate(recent)
    payload = {
        "generated_at": generated.isoformat(),
        "generated_at_jst": generated.astimezone(JST).isoformat(),
        "period_start": threshold.isoformat(),
        "lookback_hours": LOOKBACK_HOURS,
        "raw_item_count": len(all_articles),
        "recent_item_count_before_dedup": len(recent),
        "article_count": len(deduped),
        "feed_status": feed_status,
        "articles": [asdict(article) for article in deduped],
    }

    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    STATUS_JSON.write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "feed_status": feed_status,
                "article_count": payload["article_count"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    OUTPUT_HTML.write_text(render_html(payload), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
