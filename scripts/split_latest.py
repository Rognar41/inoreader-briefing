#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"

INPUT_JSON = DOCS_DIR / "latest.json"

OUTPUT_META_JSON = DOCS_DIR / "latest-meta.json"
OUTPUT_00_JSON = DOCS_DIR / "latest-00.json"
OUTPUT_06_JSON = DOCS_DIR / "latest-06.json"

FOLDER_00 = "00_毎日確認"
FOLDER_06 = "06_左派ニュース・社会主義戦略"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    payload = json.loads(
        INPUT_JSON.read_text(encoding="utf-8")
    )

    articles = payload.get("articles", [])

    articles_00 = [
        article
        for article in articles
        if FOLDER_00 in article.get("source_folders", [])
    ]

    articles_06 = [
        article
        for article in articles
        if FOLDER_06 in article.get("source_folders", [])
    ]

    common = {
        "generated_at": payload.get("generated_at"),
        "generated_at_jst": payload.get("generated_at_jst"),
        "period_start": payload.get("period_start"),
        "lookback_hours": payload.get("lookback_hours"),
    }

    meta_payload = {
        **common,
        "raw_item_count": payload.get("raw_item_count", 0),
        "recent_item_count_before_dedup": payload.get(
            "recent_item_count_before_dedup",
            0,
        ),
        "article_count": payload.get(
            "article_count",
            len(articles),
        ),
        "article_count_00": len(articles_00),
        "article_count_06": len(articles_06),
        "feed_status": payload.get("feed_status", []),
    }

    payload_00 = {
        **common,
        "folder": FOLDER_00,
        "article_count": len(articles_00),
        "articles": articles_00,
    }

    payload_06 = {
        **common,
        "folder": FOLDER_06,
        "article_count": len(articles_06),
        "articles": articles_06,
    }

    write_json(
        OUTPUT_META_JSON,
        meta_payload,
    )

    write_json(
        OUTPUT_00_JSON,
        payload_00,
    )

    write_json(
        OUTPUT_06_JSON,
        payload_06,
    )

    print(
        json.dumps(
            {
                "generated_at_jst": common["generated_at_jst"],
                "article_count": meta_payload["article_count"],
                "article_count_00": len(articles_00),
                "article_count_06": len(articles_06),
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
