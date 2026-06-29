# 修改日志（CHANGELOG）

记录对 LeetCode Coach 的功能改动，方便日后回顾和继续迭代。
格式：日期 + 改了什么 + 为什么。

---

## 2026-06-17 — 新增「🤖 AI 教练」功能

**目标**：在 web 端直接获得 AI 刷题辅导（README「后续可扩展」里的「AI 思路诊断 / 题解点评」）。

**核心方案**：复用本机已装的 `claude-code-internal` CLI 无头模式
（`node <cli> -p "<prompt>"`），用的就是和终端里完全相同的模型与登录，
无需 API key、零额外成本。

### 新增文件 `coach.py`（LLM 调用层）
- `available()`：探测 CLI 是否可用，返回 `(bool, 友好说明)`。
- `ask(messages, problem=None)`：拼系统提示词 + 题目上下文 + 对话历史，
  调 CLI 返回教练回复。任何异常都转成 `⚠️ …` 字符串，界面不崩。
- `COACH_SYSTEM`：教学风格 = 苏格拉底式阶梯提示（不直接甩答案，Python 讲解）。
- 关键参数 `--disallowed-tools Bash,Edit,Write,…`：禁用所有工具。
  **原因**：不禁的话无头实例会把 prompt 里的内容误当成「任务」去执行而跑偏
  （实测复现过，禁用后 3/3 稳定）。
- `--no-session-persistence`：每次调用不落盘，互不干扰。

### 改动 `app.py`
- 导航 `PAGES` 加 `"🤖 AI 教练": "coach"`，新增 `elif page == "coach"` 分支：
  聊天式界面（`st.chat_message` / `st.chat_input`），对话历史存
  `st.session_state["coach_msgs"]`，可关联一道题、可清空对话。
- 复习页（逐题卡片）、题库页（每行）各加「🤖 问教练」按钮：
  写入 `coach_problem` 上下文 + 设 `_goto_coach` 标志后 `st.rerun()`。

### 跳转 bug 修复（同日）
- **现象**：点「问教练」跳到教练页后，一交互就弹回原页面。
- **根因**：原来用一次性标志只在「点击后那一帧」强制切页，但侧边栏导航
  radio 仍停在原页，下次刷新就被拉回。
- **修法**：导航 radio 加 `key="nav"`；按钮设 `_goto_coach` 标志后，
  在 **radio 渲染之前** 把 `st.session_state["nav"]` 改成「🤖 AI 教练」。
  （Streamlit 不允许 widget 渲染后再改它的 key，所以必须在渲染前消费标志。）

### Code review 后的清理（同日）
- 删掉 `coach.py` 里没用到的 `import json`（曾打算解析 stream-json，后改纯文本）。
- 关联题目的笔记（note）不再全文塞进 prompt：用户笔记常含「思路：用哈希表」
  这类剧透，会破坏苏格拉底式引导。现在只告诉教练「用户写过私人笔记，别替他说出来」。

### 端口固定（同日补充）
- 新增 `.streamlit/config.toml`，把端口固定为 **8600**（避开默认 8501 偶尔被
  残留进程占用导致启动失败的问题）。要换端口改这个文件里的数字即可。

---

## 2026-06-29 — 跨电脑迁移支持

为了把项目迁到另一台电脑，做了以下改动：
- **`coach.py` 路径通用化**：删掉写死的本机 CLI 路径，改为「环境变量 `COACH_CLAUDE_CLI`
  → PATH → nvm/npm 全局目录 glob」三级探测。新机没装 claude-code-internal 时
  AI 教练页优雅提示「暂不可用」，复习/题库/弱点等功能照常。
- **新增 `requirements.txt`**：streamlit==1.50.0, pandas==2.3.3（其余均标准库）。
- **新增 `setup.sh`**：新机一键重建 .venv + 装依赖。
- **打包约定**：迁移用 tar 包**不含** `.venv`（macOS 专属二进制，换机必废）和
  `leetcode.db`（个人数据）。新机流程：解压 → `./setup.sh` → `./start.sh`。

### 已知限制 / 二期可做
- 非流式：点完等几秒一次性出结果（spinner 占位）。流式需用
  `--output-format stream-json` 增量解析。
- 多轮对话每次重发全部历史（无头 CLI 无状态），轮次多了会变慢。
- 可加「教练页底部一键把这道题录入练习」形成闭环（复用 `db.add_problem`）。
