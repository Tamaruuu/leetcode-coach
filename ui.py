"""公共 UI 组件 & 全局样式 —— 让 Streamlit 界面更好看、更统一。

所有页面都从这里取 CSS 注入和卡片/徽章组件，保持 app.py 干净。
"""

import streamlit as st

DIFF_COLOR = {
    "简单": "#00b8a3",
    "中等": "#ffb800",
    "困难": "#ff375f",
}

QUALITY_LABEL = {5: "秒了", 3: "想了挺久", 2: "看了提示", 0: "不会"}


def inject_css():
    """注入全局样式：卡片、徽章、KPI、收紧留白等。只需在每次脚本开头调一次。"""
    st.markdown(
        """
        <style>
        /* 收紧顶部留白 */
        .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1100px; }

        /* KPI 卡片 */
        .kpi {
            background: linear-gradient(135deg, #ffffff 0%, #f6f8fc 100%);
            border: 1px solid #e8ecf3; border-radius: 16px;
            padding: 18px 20px; box-shadow: 0 1px 3px rgba(16,24,40,.06);
        }
        .kpi .label { color:#667085; font-size:.82rem; font-weight:600; letter-spacing:.02em;}
        .kpi .value { color:#101828; font-size:2.0rem; font-weight:800; line-height:1.1; margin-top:4px;}
        .kpi .sub   { color:#98a2b3; font-size:.78rem; margin-top:2px;}

        /* 题目卡片 */
        .pcard {
            border:1px solid #e8ecf3; border-radius:14px; padding:14px 18px;
            margin-bottom:10px; background:#fff; box-shadow:0 1px 2px rgba(16,24,40,.04);
        }
        .pcard:hover { box-shadow:0 4px 14px rgba(16,24,40,.10); }
        .pcard .title { font-size:1.02rem; font-weight:700; color:#101828;}
        .pcard .meta  { color:#98a2b3; font-size:.82rem; margin-top:3px;}

        /* 难度徽章 */
        .badge {
            display:inline-block; padding:2px 10px; border-radius:999px;
            font-size:.74rem; font-weight:700; color:#fff;
        }
        /* 标签 chip */
        .chip {
            display:inline-block; padding:2px 9px; margin:2px 4px 2px 0;
            border-radius:8px; background:#eef2ff; color:#3538cd;
            font-size:.74rem; font-weight:600;
        }
        /* 大复习卡 */
        .reviewcard {
            border:1px solid #e8ecf3; border-radius:20px; padding:30px 34px;
            background:linear-gradient(135deg,#ffffff,#f7f9fd);
            box-shadow:0 4px 20px rgba(16,24,40,.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def difficulty_badge(diff: str) -> str:
    color = DIFF_COLOR.get(diff, "#98a2b3")
    return f'<span class="badge" style="background:{color}">{diff or "?"}</span>'


def chips(patterns_str: str) -> str:
    if not patterns_str:
        return '<span class="meta">无标签</span>'
    return "".join(
        f'<span class="chip">{p}</span>' for p in patterns_str.split(",") if p
    )


def kpi(label: str, value, sub: str = ""):
    st.markdown(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def heatmap_html(daily_counts: dict, weeks: int = 12):
    """GitHub 风格练习热力图（近 N 周）。daily_counts: {iso_date: count}。"""
    from datetime import date, timedelta

    today = date.today()
    # 对齐到本周末，往前推 weeks 周
    total_days = weeks * 7
    start = today - timedelta(days=total_days - 1)
    # 让起点落在周一
    start -= timedelta(days=start.weekday())

    def color(c):
        if c <= 0:
            return "#ebedf0"
        if c == 1:
            return "#9be9a8"
        if c == 2:
            return "#40c463"
        if c <= 4:
            return "#30a14e"
        return "#216e39"

    cells = ""
    d = start
    cols = []
    while d <= today:
        week = []
        for _ in range(7):
            c = daily_counts.get(d.isoformat(), 0)
            week.append(
                f'<div title="{d.isoformat()}: {c} 次" '
                f'style="width:13px;height:13px;border-radius:3px;'
                f'background:{color(c)};margin:2px;"></div>'
            )
            d += timedelta(days=1)
            if d > today:
                break
        cols.append(f'<div style="display:flex;flex-direction:column">{"".join(week)}</div>')
    grid = f'<div style="display:flex">{"".join(cols)}</div>'
    legend = (
        '<div style="display:flex;align-items:center;gap:6px;margin-top:8px;'
        'color:#98a2b3;font-size:.75rem">少'
        + "".join(
            f'<div style="width:11px;height:11px;border-radius:3px;background:{c}"></div>'
            for c in ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
        )
        + "多</div>"
    )
    return grid + legend
