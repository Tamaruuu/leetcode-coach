"""SQLite 数据层 —— 所有读写都走这里，界面层不直接碰 SQL。

表设计：
  problems   题目本身（一题一行）
  attempts   每次做题/复习的流水记录（一题多行，用于统计趋势）
problems 表里内嵌了 SM-2 的当前状态字段，方便快速查"今天该复习什么"。
"""

import sqlite3
from datetime import date
from pathlib import Path

import srs

DB_PATH = Path(__file__).parent / "leetcode.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS problems (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                number        INTEGER,
                title         TEXT NOT NULL,
                difficulty    TEXT,                 -- 简单 / 中等 / 困难
                url           TEXT,
                patterns      TEXT,                 -- 逗号分隔的模式标签
                note          TEXT,                 -- 思路触发点 / 易错点
                created_at    TEXT,
                -- SM-2 状态
                repetitions   INTEGER DEFAULT 0,
                ease_factor   REAL    DEFAULT 2.5,
                interval_days INTEGER DEFAULT 0,
                next_review   TEXT                  -- 下次复习日期 (ISO)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id  INTEGER NOT NULL,
                attempt_date TEXT,
                outcome     TEXT,                   -- 秒了/想了挺久/看了提示/不会
                quality     INTEGER,
                minutes     INTEGER,                -- 本次用时
                note        TEXT,
                FOREIGN KEY (problem_id) REFERENCES problems(id)
            );
            """
        )


def add_problem(number, title, difficulty, url, patterns, note):
    today = date.today().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO problems
               (number, title, difficulty, url, patterns, note, created_at, next_review)
               VALUES (?,?,?,?,?,?,?,?)""",
            (number, title, difficulty, url, ",".join(patterns), note, today, today),
        )
        return cur.lastrowid


def log_attempt(problem_id, outcome, minutes, note):
    """记录一次做题/复习，并据此推进该题的 SM-2 状态。"""
    quality = srs.OUTCOME_TO_QUALITY[outcome]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT repetitions, ease_factor, interval_days FROM problems WHERE id=?",
            (problem_id,),
        ).fetchone()
        reps, ef, interval, next_date = srs.review(
            row["repetitions"], row["ease_factor"], row["interval_days"], quality
        )
        conn.execute(
            """UPDATE problems
               SET repetitions=?, ease_factor=?, interval_days=?, next_review=?
               WHERE id=?""",
            (reps, ef, interval, next_date.isoformat(), problem_id),
        )
        conn.execute(
            """INSERT INTO attempts
               (problem_id, attempt_date, outcome, quality, minutes, note)
               VALUES (?,?,?,?,?,?)""",
            (problem_id, date.today().isoformat(), outcome, quality, minutes, note),
        )


def get_due_problems():
    """今天（含之前）该复习的题。"""
    today = date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM problems WHERE next_review <= ? ORDER BY next_review ASC",
            (today,),
        ).fetchall()


def get_all_problems():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM problems ORDER BY created_at DESC"
        ).fetchall()


def get_all_attempts():
    with get_conn() as conn:
        return conn.execute(
            """SELECT a.*, p.title, p.patterns, p.difficulty
               FROM attempts a JOIN problems p ON a.problem_id = p.id
               ORDER BY a.attempt_date DESC"""
        ).fetchall()


# ---------------------------------------------------------------------------
# 题库 (catalog) —— 由 fetch_problems.py 拉取填充
# ---------------------------------------------------------------------------
DIFFICULTY_CN = {"EASY": "简单", "MEDIUM": "中等", "HARD": "困难"}


def catalog_count():
    """题库题数；表不存在则返回 0。"""
    with get_conn() as conn:
        try:
            row = conn.execute("SELECT COUNT(*) c FROM catalog").fetchone()
            return row["c"]
        except sqlite3.OperationalError:
            return 0


def search_catalog(keyword, limit=50):
    """按题号或中/英标题模糊搜索题库。"""
    kw = f"%{keyword.strip()}%"
    with get_conn() as conn:
        try:
            return conn.execute(
                """SELECT * FROM catalog
                   WHERE frontend_id LIKE ? OR title_cn LIKE ? OR title_en LIKE ?
                   ORDER BY CAST(frontend_id AS INTEGER) ASC
                   LIMIT ?""",
                (kw, kw, kw, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []


def catalog_url(slug):
    return f"https://leetcode.cn/problems/{slug}/"


def browse_catalog(keyword="", difficulty="", tag="", page=0, page_size=20):
    """分页浏览题库，支持按关键词/难度/标签筛选。

    返回 (rows, total_count)。difficulty 传 EASY/MEDIUM/HARD，空串表示不限。
    """
    where, params = [], []
    if keyword.strip():
        kw = f"%{keyword.strip()}%"
        where.append("(frontend_id LIKE ? OR title_cn LIKE ? OR title_en LIKE ?)")
        params += [kw, kw, kw]
    if difficulty:
        where.append("difficulty = ?")
        params.append(difficulty)
    if tag:
        where.append("tags LIKE ?")
        params.append(f"%{tag}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with get_conn() as conn:
        try:
            total = conn.execute(
                f"SELECT COUNT(*) c FROM catalog {clause}", params
            ).fetchone()["c"]
            rows = conn.execute(
                f"""SELECT * FROM catalog {clause}
                    ORDER BY CAST(frontend_id AS INTEGER) ASC, frontend_id ASC
                    LIMIT ? OFFSET ?""",
                params + [page_size, page * page_size],
            ).fetchall()
            return rows, total
        except sqlite3.OperationalError:
            return [], 0


def all_catalog_tags():
    """题库里出现过的所有官方标签（去重排序），用于筛选下拉。"""
    with get_conn() as conn:
        try:
            rows = conn.execute("SELECT tags FROM catalog WHERE tags != ''").fetchall()
        except sqlite3.OperationalError:
            return []
    seen = set()
    for r in rows:
        for t in r["tags"].split(","):
            if t:
                seen.add(t)
    return sorted(seen)


def is_added(frontend_id):
    """该题是否已加入我的练习列表（problems 表，按题号匹配）。"""
    if not str(frontend_id).isdigit():
        return False
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM problems WHERE number = ? LIMIT 1", (int(frontend_id),)
        ).fetchone()
        return row is not None


# ---------------------------------------------------------------------------
# 统计（首页仪表盘用）
# ---------------------------------------------------------------------------
def get_stats():
    """返回首页 KPI：总题数、今日待复习、累计练习次数、平均掌握度、难度分布。"""
    today = date.today().isoformat()
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM problems").fetchone()["c"]
        due = conn.execute(
            "SELECT COUNT(*) c FROM problems WHERE next_review <= ?", (today,)
        ).fetchone()["c"]
        attempts = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
        avg_q = conn.execute("SELECT AVG(quality) q FROM attempts").fetchone()["q"]
        diff_rows = conn.execute(
            "SELECT difficulty, COUNT(*) c FROM problems GROUP BY difficulty"
        ).fetchall()
    difficulty = {r["difficulty"] or "未知": r["c"] for r in diff_rows}
    return {
        "total": total,
        "due": due,
        "attempts": attempts,
        "avg_quality": round(avg_q, 2) if avg_q is not None else None,
        "difficulty": difficulty,
    }


def get_streak():
    """连续练习天数（含今天/昨天起算）。今天没练但昨天练了仍算 streak 延续。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT attempt_date FROM attempts ORDER BY attempt_date DESC"
        ).fetchall()
    days = {r["attempt_date"] for r in rows}
    if not days:
        return 0
    from datetime import timedelta

    today = date.today()
    # 起点：今天练了就从今天算，否则若昨天练了从昨天算，否则 streak=0
    if today.isoformat() in days:
        cursor = today
    elif (today - timedelta(days=1)).isoformat() in days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_daily_counts(days=84):
    """近 N 天每天的练习次数 {date_iso: count}，用于热力图。"""
    from datetime import timedelta

    start = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT attempt_date, COUNT(*) c FROM attempts
               WHERE attempt_date >= ? GROUP BY attempt_date""",
            (start,),
        ).fetchall()
    return {r["attempt_date"]: r["c"] for r in rows}


def weakest_patterns(limit=3):
    """平均质量最低的模式（至少练过 1 次），返回 [(模式, 平均质量, 次数)]。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.patterns, a.quality FROM attempts a
               JOIN problems p ON a.problem_id = p.id
               WHERE p.patterns != ''"""
        ).fetchall()
    from collections import defaultdict

    agg = defaultdict(list)
    for r in rows:
        for pat in (r["patterns"] or "").split(","):
            if pat:
                agg[pat].append(r["quality"])
    scored = [
        (pat, round(sum(qs) / len(qs), 2), len(qs)) for pat, qs in agg.items()
    ]
    scored.sort(key=lambda x: x[1])
    return scored[:limit]


# ---------------------------------------------------------------------------
# 编辑 / 删除（我的题目页用）
# ---------------------------------------------------------------------------
def get_problem(problem_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM problems WHERE id=?", (problem_id,)
        ).fetchone()


def update_problem(problem_id, title, difficulty, url, patterns, note):
    with get_conn() as conn:
        conn.execute(
            """UPDATE problems
               SET title=?, difficulty=?, url=?, patterns=?, note=?
               WHERE id=?""",
            (title, difficulty, url, ",".join(patterns), note, problem_id),
        )


def delete_problem(problem_id):
    """删除题目及其所有做题记录。"""
    with get_conn() as conn:
        conn.execute("DELETE FROM attempts WHERE problem_id=?", (problem_id,))
        conn.execute("DELETE FROM problems WHERE id=?", (problem_id,))


def set_next_review(problem_id, next_review_iso):
    """手动设置某题的下次复习日期。"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE problems SET next_review=? WHERE id=?",
            (next_review_iso, problem_id),
        )
