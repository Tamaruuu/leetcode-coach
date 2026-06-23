"""LeetCode Coach —— AI 时代的个人刷题教练（Streamlit，零前端代码）。

启动：  ./start.sh   或   ./.venv/bin/streamlit run app.py

页面：
  🏠 总览     KPI + 练习热力图 + 薄弱模式速览
  📅 复习     逐题专注卡片，打分自动跳下一题（间隔重复核心）
  📖 题库     浏览/筛选 4000+ 力扣题，一键加入练习
  ➕ 添加     搜索式录入新题
  📊 弱点     按模式统计掌握度
  📚 我的题目  卡片列表，支持编辑 / 删除 / 手动改复习日
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import coach
import db
import srs
import ui
from patterns import ALL_PATTERNS, PATTERN_GROUPS, group_of

st.set_page_config(page_title="LeetCode Coach", page_icon="🧠", layout="wide")
db.init_db()
ui.inject_css()

DIFFS = ["简单", "中等", "困难"]


def tag_picker(key_prefix, default=None):
    """一个可搜索的多选标签选择器，取代 7 个分组 multiselect。"""
    default = default or []
    return st.multiselect(
        "模式标签（可搜索，弱点分析的基础）",
        ALL_PATTERNS,
        default=[d for d in default if d in ALL_PATTERNS],
        key=f"{key_prefix}_tags",
        placeholder="输入关键字搜索，如『双指针』『DP』…",
    )


# ============================================================================
# 侧边栏导航
# ============================================================================
st.sidebar.title("🧠 LeetCode Coach")
PAGES = {
    "🏠 总览": "home",
    "📅 复习": "review",
    "📖 题库": "browse",
    "➕ 添加": "add",
    "📊 弱点": "weak",
    "📚 我的题目": "mine",
    "🤖 AI 教练": "coach",
}
_labels = list(PAGES.keys())
# 其它页点「🤖 问教练」会设置这个标志：在 radio 渲染前消费掉，用它决定初始选中页，
# 这样跳转后停在教练页、后续刷新也不会弹回（Streamlit 不允许 radio 渲染后再改其 key）。
if st.session_state.pop("_goto_coach", False):
    st.session_state["nav"] = "🤖 AI 教练"
choice = st.sidebar.radio(
    "导航", _labels, label_visibility="collapsed", key="nav"
)
page = PAGES[choice]
st.sidebar.markdown("---")
_s = db.get_stats()
st.sidebar.metric("今日待复习", _s["due"])
st.sidebar.metric("🔥 连续天数", db.get_streak())
st.sidebar.caption("成为大师靠的是**间隔重复 + 弱点定位**，不是刷题量。")


# ============================================================================
# 🏠 总览
# ============================================================================
if page == "home":
    st.title("🏠 总览")
    s = db.get_stats()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi("今日待复习", s["due"], "去『复习』清空它")
    with c2:
        ui.kpi("🔥 连续天数", db.get_streak(), "每天练一点")
    with c3:
        ui.kpi("累计练习", s["attempts"], f'{s["total"]} 道题在练')
    with c4:
        q = s["avg_quality"]
        ui.kpi("平均掌握度", f"{q}/5" if q is not None else "—", "5=秒了 0=不会")

    st.markdown("### ")
    if s["due"] > 0:
        if st.button(f"▶️ 开始今日复习（{s['due']} 题）", type="primary"):
            st.session_state["_goto_review"] = True
            st.rerun()

    left, right = st.columns([3, 2])
    with left:
        st.subheader("📈 练习热力图（近 12 周）")
        st.markdown(ui.heatmap_html(db.get_daily_counts(84), weeks=12),
                    unsafe_allow_html=True)
    with right:
        st.subheader("🔴 最薄弱的模式")
        weak = db.weakest_patterns(5)
        if not weak:
            st.caption("还没有带标签的练习记录。录题时记得打模式标签。")
        else:
            for pat, avg_q, cnt in weak:
                st.markdown(
                    f"**{pat}** &nbsp; <span style='color:#ff375f'>{avg_q}/5</span> "
                    f"<span style='color:#98a2b3'>· {cnt} 次</span>",
                    unsafe_allow_html=True,
                )

    if s["difficulty"]:
        st.subheader("难度分布")
        cols = st.columns(len(s["difficulty"]))
        for col, (d, c) in zip(cols, s["difficulty"].items()):
            with col:
                ui.kpi(d, c)

    # 从首页按钮跳转
    if st.session_state.pop("_goto_review", False):
        pass


# ============================================================================
# 📅 复习（逐题专注模式）
# ============================================================================
elif page == "review":
    st.title("📅 复习")
    due = db.get_due_problems()

    if not due:
        st.success("🎉 今天没有要复习的题了！去『题库』挑新题，或休息一下。")
    else:
        mode = st.radio(
            "模式", ["🎯 逐题专注", "📋 全部展开"], horizontal=True,
            label_visibility="collapsed",
        )

        if mode == "🎯 逐题专注":
            # 用 session 记录当前进度
            idx = st.session_state.get("review_idx", 0)
            idx = min(idx, len(due) - 1)
            total = len(due)
            p = due[idx]

            st.progress((idx) / total, text=f"进度 {idx}/{total}")
            with st.container():
                st.markdown('<div class="reviewcard">', unsafe_allow_html=True)
                st.markdown(
                    f"### #{p['number'] or '?'} {p['title']} "
                    f"{ui.difficulty_badge(p['difficulty'])}",
                    unsafe_allow_html=True,
                )
                st.markdown(ui.chips(p["patterns"]), unsafe_allow_html=True)
                if p["url"]:
                    st.markdown(f"🔗 [在力扣打开]({p['url']})")

                with st.expander("💡 显示我的笔记 / 思路触发点"):
                    st.write(p["note"] or "（这道题还没写笔记）")

                st.markdown("**这次表现如何？**（打完自动跳下一题）")
                cols = st.columns(4)
                outcomes = srs.OUTCOMES  # 秒了/想了挺久/看了提示/不会
                emojis = ["🚀", "🤔", "💡", "😵"]
                for col, oc, em in zip(cols, outcomes, emojis):
                    if col.button(f"{em} {oc}", key=f"oc_{idx}_{oc}",
                                  width="stretch"):
                        db.log_attempt(p["id"], oc, 0, "")
                        if idx + 1 >= total:
                            st.session_state["review_idx"] = 0
                            st.session_state["review_done"] = True
                        else:
                            st.session_state["review_idx"] = idx + 1
                        st.rerun()
                if st.button("🤖 问教练", key=f"coach_{idx}", width="stretch"):
                    st.session_state["coach_problem"] = {
                        "number": p["number"], "title": p["title"],
                        "difficulty": p["difficulty"], "patterns": p["patterns"],
                        "url": p["url"], "note": p["note"],
                    }
                    st.session_state["_goto_coach"] = True
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.pop("review_done", False):
                st.balloons()
                st.success("🎉 今日复习全部完成！")

        else:  # 全部展开
            st.write(f"今天有 **{len(due)}** 道题该复习：")
            for p in due:
                with st.expander(
                    f"#{p['number'] or '?'} · {p['title']} · {p['difficulty'] or ''}"
                ):
                    st.markdown(ui.chips(p["patterns"]), unsafe_allow_html=True)
                    if p["url"]:
                        st.markdown(f"🔗 [打开题目]({p['url']})")
                    if p["note"]:
                        st.info(f"💡 {p['note']}")
                    with st.form(f"review_{p['id']}"):
                        c1, c2 = st.columns([2, 1])
                        oc = c1.radio("表现", srs.OUTCOMES, horizontal=True,
                                      key=f"r_{p['id']}")
                        mins = c2.number_input("用时(分)", 0, 300, 15,
                                               key=f"m_{p['id']}")
                        if st.form_submit_button("✅ 提交"):
                            db.log_attempt(p["id"], oc, mins, "")
                            st.rerun()


# ============================================================================
# 📖 题库浏览
# ============================================================================
elif page == "browse":
    st.title("📖 题库")
    n = db.catalog_count()
    if n == 0:
        st.warning(
            "本地题库为空。先在终端运行：\n\n"
            "`cd ~/leetcode-coach && ./.venv/bin/python fetch_problems.py`"
        )
    else:
        @st.dialog("➕ 加入练习")
        def add_dialog(prob):
            st.markdown(
                f"**#{prob['frontend_id']} {prob['title_cn']}** "
                f"{ui.difficulty_badge(db.DIFFICULTY_CN.get(prob['difficulty'], '中等'))}",
                unsafe_allow_html=True,
            )
            st.caption(f"力扣官方标签：{prob['tags'] or '无'}")
            with st.form("quick_add"):
                official = [t for t in (prob["tags"] or "").split(",")
                            if t in ALL_PATTERNS]
                selected = tag_picker("dlg", default=official)
                note = st.text_area("笔记（思路触发点、易错点）")
                fc1, fc2 = st.columns([2, 1])
                first_outcome = fc1.radio("首次表现", srs.OUTCOMES,
                                          horizontal=True, index=1)
                first_minutes = fc2.number_input("用时(分)", 0, 300, 20)
                if st.form_submit_button("✅ 确认加入", type="primary"):
                    num = int(prob["frontend_id"]) if prob["frontend_id"].isdigit() else 0
                    diff = db.DIFFICULTY_CN.get(prob["difficulty"], "中等")
                    pid = db.add_problem(num, prob["title_cn"], diff,
                                         db.catalog_url(prob["slug"]), selected, note)
                    db.log_attempt(pid, first_outcome, first_minutes, "")
                    st.success(f"已加入《{prob['title_cn']}》！")
                    st.rerun()

        st.caption(f"题库共 {n} 道题。筛选浏览，点『➕ 加入练习』。")
        f1, f2, f3 = st.columns([2, 1, 2])
        kw = f1.text_input("🔍 关键词（题号/标题）", "")
        diff_label = f2.selectbox("难度", ["全部"] + DIFFS)
        diff_map = {"全部": "", "简单": "EASY", "中等": "MEDIUM", "困难": "HARD"}
        tag = f3.selectbox("官方标签", ["全部"] + db.all_catalog_tags())
        tag_val = "" if tag == "全部" else tag

        PAGE_SIZE = 20
        if "browse_page" not in st.session_state:
            st.session_state.browse_page = 0
        filt_key = (kw, diff_label, tag)
        if st.session_state.get("browse_filt") != filt_key:
            st.session_state.browse_filt = filt_key
            st.session_state.browse_page = 0

        rows, total = db.browse_catalog(
            keyword=kw, difficulty=diff_map[diff_label], tag=tag_val,
            page=st.session_state.browse_page, page_size=PAGE_SIZE)
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        cur = st.session_state.browse_page
        st.write(f"共 **{total}** 题，第 {cur + 1}/{pages} 页：")

        for r in rows:
            diff_cn = db.DIFFICULTY_CN.get(r["difficulty"], r["difficulty"])
            added = db.is_added(r["frontend_id"])
            c1, c2, c3 = st.columns([7, 1.5, 1.5])
            with c1:
                st.markdown(
                    f'<div class="pcard"><span class="title">'
                    f'#{r["frontend_id"]} <a href="{db.catalog_url(r["slug"])}" '
                    f'target="_blank">{r["title_cn"]}</a></span> '
                    f'{ui.difficulty_badge(diff_cn)} '
                    f'{"✅" if added else ""}<div class="meta">{r["tags"] or "无标签"}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            with c2:
                if added:
                    st.caption("已加入")
                elif st.button("➕ 加入", key=f"add_{r['frontend_id']}",
                               width="stretch"):
                    add_dialog(dict(r))
            with c3:
                if st.button("🤖 问教练", key=f"coach_browse_{r['frontend_id']}",
                             width="stretch"):
                    num = int(r["frontend_id"]) if str(r["frontend_id"]).isdigit() else 0
                    st.session_state["coach_problem"] = {
                        "number": num, "title": r["title_cn"], "difficulty": diff_cn,
                        "patterns": r["tags"] or "", "url": db.catalog_url(r["slug"]),
                        "note": "",
                    }
                    st.session_state["_goto_coach"] = True
                    st.rerun()

        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("⬅️ 上一页", disabled=cur <= 0, width="stretch"):
            st.session_state.browse_page -= 1
            st.rerun()
        p2.markdown(f"<div style='text-align:center;padding-top:6px'>第 {cur + 1}/{pages} 页</div>",
                    unsafe_allow_html=True)
        if p3.button("下一页 ➡️", disabled=cur >= pages - 1, width="stretch"):
            st.session_state.browse_page += 1
            st.rerun()


# ============================================================================
# ➕ 添加题目（搜索式录入）
# ============================================================================
elif page == "add":
    st.title("➕ 添加题目")
    n = db.catalog_count()
    if n:
        st.caption(f"📚 题库共 {n} 道题，可搜索带出标题/难度/链接/官方标签。")

    picked = None
    kw = st.text_input("🔍 搜索题库（题号 / 中文 / 英文）", "")
    if kw:
        results = db.search_catalog(kw, limit=50)
        if results:
            options = {
                f"#{r['frontend_id']} {r['title_cn']} "
                f"({db.DIFFICULTY_CN.get(r['difficulty'], r['difficulty'])})": r
                for r in results
            }
            ch = st.selectbox(f"找到 {len(results)} 题：", list(options.keys()))
            picked = options[ch]
            st.markdown(
                f"{ui.difficulty_badge(db.DIFFICULTY_CN.get(picked['difficulty'],'中等'))} "
                f"[{picked['title_cn']}]({db.catalog_url(picked['slug'])}) · "
                f"官方标签：{picked['tags'] or '无'}",
                unsafe_allow_html=True,
            )
        else:
            st.info("题库没找到，可在下方手动录入。")

    default_tags = [t for t in (picked["tags"].split(",") if picked else [])
                    if t in ALL_PATTERNS]
    selected = tag_picker("add", default=default_tags)

    with st.form("add"):
        c1, c2, c3 = st.columns([1, 3, 1])
        default_num = int(picked["frontend_id"]) if (picked and picked["frontend_id"].isdigit()) else 0
        number = c1.number_input("题号", 0, 100000, default_num)
        title = c2.text_input("标题 *", picked["title_cn"] if picked else "")
        default_diff = db.DIFFICULTY_CN.get(picked["difficulty"], "中等") if picked else "中等"
        difficulty = c3.selectbox("难度", DIFFS, index=DIFFS.index(default_diff))
        url = st.text_input("链接", db.catalog_url(picked["slug"]) if picked else "")
        note = st.text_area("初始笔记（思路触发点、易错点）")
        fc1, fc2 = st.columns([2, 1])
        first_outcome = fc1.radio("首次表现", srs.OUTCOMES, horizontal=True, index=1)
        first_minutes = fc2.number_input("首次用时(分)", 0, 300, 20)
        if st.form_submit_button("保存", type="primary"):
            if not title:
                st.error("标题不能为空")
            else:
                pid = db.add_problem(number, title, difficulty, url, selected, note)
                db.log_attempt(pid, first_outcome, first_minutes, "")
                st.success(f"已添加《{title}》并安排了首次复习。")


# ============================================================================
# 📊 弱点分析
# ============================================================================
elif page == "weak":
    st.title("📊 弱点分析")
    attempts = db.get_all_attempts()
    if not attempts:
        st.info("还没有做题记录。先去添加几道题吧。")
    else:
        rows = []
        for a in attempts:
            pats = (a["patterns"] or "").split(",") if a["patterns"] else ["未标记"]
            for pat in pats:
                if pat:
                    rows.append({"模式": pat, "质量": a["quality"],
                                 "用时": a["minutes"] or 0})
        df = pd.DataFrame(rows)
        agg = (df.groupby("模式")
               .agg(练习次数=("质量", "size"), 平均掌握度=("质量", "mean"),
                    平均用时=("用时", "mean"))
               .reset_index().sort_values("平均掌握度"))
        agg["平均掌握度"] = agg["平均掌握度"].round(2)
        agg["平均用时"] = agg["平均用时"].round(1)

        st.subheader("🔴 最薄弱的模式")
        st.caption("掌握度 5=秒了 3=想了挺久 2=看提示 0=不会。优先攻克下面这些。")
        st.dataframe(agg.head(5), width="stretch", hide_index=True)

        st.subheader("各模式掌握度")
        st.bar_chart(agg.set_index("模式")["平均掌握度"], horizontal=True)

        st.subheader("全部明细")
        st.dataframe(agg, width="stretch", hide_index=True)


# ============================================================================
# 📚 我的题目（编辑 / 删除）
# ============================================================================
elif page == "mine":
    st.title("📚 我的题目")
    problems = db.get_all_problems()
    if not problems:
        st.info("还没有题目。去『题库』或『添加』录入吧。")
    else:
        @st.dialog("✏️ 编辑题目")
        def edit_dialog(p):
            cur_tags = [t for t in (p["patterns"] or "").split(",") if t]
            with st.form("edit_form"):
                title = st.text_input("标题", p["title"])
                difficulty = st.selectbox(
                    "难度", DIFFS,
                    index=DIFFS.index(p["difficulty"]) if p["difficulty"] in DIFFS else 1)
                url = st.text_input("链接", p["url"] or "")
                selected = st.multiselect("模式标签", ALL_PATTERNS,
                                          default=[t for t in cur_tags if t in ALL_PATTERNS])
                note = st.text_area("笔记", p["note"] or "")
                nr = st.date_input(
                    "下次复习日",
                    value=date.fromisoformat(p["next_review"]) if p["next_review"] else date.today())
                s1, s2 = st.columns(2)
                if s1.form_submit_button("💾 保存", type="primary"):
                    db.update_problem(p["id"], title, difficulty, url, selected, note)
                    db.set_next_review(p["id"], nr.isoformat())
                    st.success("已保存")
                    st.rerun()
                if s2.form_submit_button("取消"):
                    st.rerun()

        @st.dialog("🗑️ 确认删除")
        def del_dialog(p):
            st.warning(f"确定删除《{p['title']}》及其所有做题记录？此操作不可撤销。")
            c1, c2 = st.columns(2)
            if c1.button("确认删除", type="primary"):
                db.delete_problem(p["id"])
                st.rerun()
            if c2.button("取消"):
                st.rerun()

        today = date.today().isoformat()
        st.caption(f"共 {len(problems)} 道题。")
        for p in problems:
            due_mark = "🔔 今日待复习" if (p["next_review"] or "") <= today else f"下次 {p['next_review']}"
            c1, c2, c3 = st.columns([7, 1.2, 1.2])
            with c1:
                st.markdown(
                    f'<div class="pcard"><span class="title">'
                    f'#{p["number"] or "?"} {p["title"]}</span> '
                    f'{ui.difficulty_badge(p["difficulty"])}<br>'
                    f'{ui.chips(p["patterns"])}'
                    f'<div class="meta">{due_mark} · 已复习 {p["repetitions"]} 次</div></div>',
                    unsafe_allow_html=True,
                )
            if c2.button("✏️", key=f"edit_{p['id']}", width="stretch"):
                edit_dialog(dict(p))
            if c3.button("🗑️", key=f"del_{p['id']}", width="stretch"):
                del_dialog(dict(p))


# ============================================================================
# 🤖 AI 教练（聊天式辅导，复用本机 Claude CLI）
# ============================================================================
elif page == "coach":
    st.title("🤖 AI 教练")
    ok, why = coach.available()
    if not ok:
        st.error(f"AI 教练暂不可用：{why}")
    else:
        st.caption("苏格拉底式辅导：先说说你的思路，卡住了我给阶梯提示；想直接看答案就说『直接讲』。")

    # --- 关联题目上下文 ---
    prob = st.session_state.get("coach_problem")
    with st.expander("📌 关联题目（可选，关联后教练更懂你在做哪题）", expanded=bool(prob)):
        if prob:
            st.markdown(
                f"当前关联：**#{prob.get('number') or '?'} {prob.get('title','')}** "
                f"{ui.difficulty_badge(prob.get('difficulty',''))}",
                unsafe_allow_html=True,
            )
            if prob.get("patterns"):
                st.markdown(ui.chips(prob["patterns"]), unsafe_allow_html=True)
            if st.button("✖️ 取消关联"):
                st.session_state.pop("coach_problem", None)
                st.rerun()
        else:
            mine = db.get_all_problems()
            opts = {"（不关联）": None}
            for p in mine:
                opts[f"#{p['number'] or '?'} {p['title']}"] = dict(p)
            sel = st.selectbox("从我的题目里选一道：", list(opts.keys()))
            if opts[sel] and st.button("关联这道题"):
                st.session_state["coach_problem"] = opts[sel]
                st.rerun()

    # --- 对话历史 ---
    msgs = st.session_state.setdefault("coach_msgs", [])
    cc1, cc2 = st.columns([1, 5])
    if cc1.button("🧹 清空对话"):
        st.session_state["coach_msgs"] = []
        st.rerun()

    for m in msgs:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.markdown(m["content"])

    user_input = st.chat_input("问教练…（比如：这题该用什么思路？/ 帮我看看这段代码）")
    if user_input:
        msgs.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("教练思考中…"):
                reply = coach.ask(msgs, st.session_state.get("coach_problem"))
            st.markdown(reply)
        msgs.append({"role": "assistant", "content": reply})
        st.session_state["coach_msgs"] = msgs
