"""从力扣中国(leetcode.cn)拉取全部题目元数据，存进本地题库表 catalog。

只拉公开元数据：题号、中英标题、难度、官方中文标签、slug(用于拼链接)。
不涉及题目正文（有版权）。

用法：  ./.venv/bin/python fetch_problems.py
首次运行约几分钟（分页拉 4000+ 题）。之后录题就能从题库搜索选择。
"""

import json
import time
import urllib.request

from db import get_conn, init_db

GRAPHQL = "https://leetcode.cn/graphql/"
QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList(categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters) {
    total
    hasMore
    questions {
      frontendQuestionId
      title
      titleCn
      titleSlug
      difficulty
      topicTags { nameTranslated name slug }
    }
  }
}
"""
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://leetcode.cn",
}
PAGE = 100


def fetch_page(skip):
    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "categorySlug": "all-code-essentials",
                "limit": PAGE,
                "skip": skip,
                "filters": {},
            },
        }
    ).encode()
    req = urllib.request.Request(GRAPHQL, data=payload, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data["data"]["problemsetQuestionList"]


def ensure_catalog_table():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog (
                frontend_id TEXT PRIMARY KEY,   -- 题号(可能含 LCP/面试题前缀，故用 TEXT)
                title_cn    TEXT,
                title_en    TEXT,
                slug        TEXT,
                difficulty  TEXT,               -- EASY/MEDIUM/HARD
                tags        TEXT                -- 官方中文标签，逗号分隔
            )
            """
        )


def upsert(questions):
    with get_conn() as conn:
        for q in questions:
            tags = ",".join(
                (t["nameTranslated"] or t["name"]) for t in q["topicTags"]
            )
            conn.execute(
                """INSERT OR REPLACE INTO catalog
                   (frontend_id, title_cn, title_en, slug, difficulty, tags)
                   VALUES (?,?,?,?,?,?)""",
                (
                    q["frontendQuestionId"],
                    q["titleCn"] or q["title"],
                    q["title"],
                    q["titleSlug"],
                    q["difficulty"],
                    tags,
                ),
            )


def main():
    init_db()
    ensure_catalog_table()
    skip, total = 0, None
    while True:
        page = fetch_page(skip)
        total = page["total"]
        qs = page["questions"]
        if not qs:
            break
        upsert(qs)
        skip += len(qs)
        print(f"  已拉取 {skip}/{total} ...")
        if not page["hasMore"] or skip >= total:
            break
        time.sleep(0.4)  # 友好限速
    print(f"✅ 题库就绪，共 {skip} 道题，存入 catalog 表。")


if __name__ == "__main__":
    main()
