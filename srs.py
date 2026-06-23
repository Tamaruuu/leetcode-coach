"""SM-2 间隔重复算法 —— 应用的核心引擎。

一道题做出来 != 掌握。SM-2（Anki 同款算法）根据你每次复习的表现，
动态计算下一次该在什么时候复习：答得越好间隔越长，答得差就重置。

每道题维护三个状态字段：
  - repetitions: 连续答好的次数
  - ease_factor: 难度因子（越大说明这题对你越简单，间隔涨得越快）
  - interval_days: 距离下次复习的天数

质量评分 quality (0~5)，对应到我们界面里 4 档表现：
  - 5  "秒了 / 一次过"
  - 3  "想了挺久才做出来"
  - 2  "看了提示才做出来"
  - 0  "完全不会 / 看题解"
"""

from datetime import date, timedelta

DEFAULT_EASE = 2.5
MIN_EASE = 1.3

# 界面表现 -> SM-2 质量分
OUTCOME_TO_QUALITY = {
    "秒了 / 一次过": 5,
    "想了挺久": 3,
    "看了提示": 2,
    "不会 / 看题解": 0,
}
OUTCOMES = list(OUTCOME_TO_QUALITY.keys())


def review(repetitions: int, ease_factor: float, interval_days: int, quality: int):
    """根据本次复习质量，计算新的 SM-2 状态。

    返回 (repetitions, ease_factor, interval_days, next_review_date)。
    """
    if quality < 3:
        # 答得不好：重置连胜，明天就再来一次
        repetitions = 0
        interval_days = 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease_factor)
        repetitions += 1

    # 更新难度因子
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(MIN_EASE, ease_factor)

    next_review_date = date.today() + timedelta(days=interval_days)
    return repetitions, ease_factor, interval_days, next_review_date
