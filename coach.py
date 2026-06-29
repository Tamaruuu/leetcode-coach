"""AI 教练调用层 —— 复用本机 Claude CLI（无头模式），界面层不直接碰 subprocess。

原理：本机装了 claude-code-internal，其无头模式
    node <cli> -p "<prompt>"
能一次性返回模型回答。Streamlit app 在后台调它，用的就是和终端里
完全相同的模型与登录，无需额外 API key、零额外成本。

对外只暴露：
    available() -> (bool, str)   探测 CLI 是否可用
    ask(messages, problem=None) -> str   发起一次对话，返回教练回复
"""

import os
import shutil
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# 定位 CLI（跨机器：不写死具体用户路径，靠环境变量 + PATH + glob 探测）
# ---------------------------------------------------------------------------
# 若本机装了 claude-code-internal 就能用 AI 教练；没装则优雅降级（页面提示暂不可用），
# 不影响复习/题库/弱点等其它功能。换电脑迁移时这段无需改动。
_CLI_GLOB = "**/claude-code-internal/dist/claude-code-internal.js"
_SEARCH_BASES = (
    Path.home() / ".nvm/versions",                 # nvm 安装的 node
    Path("/usr/local/lib/node_modules"),           # npm 全局（Intel mac / Linux）
    Path("/opt/homebrew/lib/node_modules"),         # npm 全局（Apple Silicon）
)


def _find_node():
    return os.environ.get("COACH_NODE") or shutil.which("node")


def _find_cli():
    """返回 claude CLI 的 js 入口路径，找不到返回 None。"""
    cand = os.environ.get("COACH_CLAUDE_CLI")
    if cand and Path(cand).exists():
        return cand
    for base in _SEARCH_BASES:
        if base.exists():
            hits = list(base.glob(_CLI_GLOB))
            if hits:
                return str(hits[0])
    return None


NODE = _find_node()
CLAUDE_CLI = _find_cli()


def available():
    """(可用?, 说明)。界面据此决定是否禁用输入框。"""
    if CLAUDE_CLI is None:
        return False, (
            "本机没装 Claude CLI（claude-code-internal），AI 教练暂不可用。"
            "装好后设环境变量 `COACH_CLAUDE_CLI` 指向其 claude-code-internal.js "
            "再重启即可；其它功能不受影响。"
        )
    if not NODE:
        return False, "没找到 node 运行时（装 node 或设环境变量 `COACH_NODE`）。"
    return True, "已就绪"


# ---------------------------------------------------------------------------
# 系统提示词 —— 即「陪练协议」，让回答符合教学预期
# ---------------------------------------------------------------------------
COACH_SYSTEM = """你是一个嵌在「LeetCode Coach」刷题 app 里的算法教练，正在 web 端实时辅导用户刷题。

用户背景：大模型算法方向，平时用 Python，代码示例一律用 Python。

教学风格（务必遵守）：
1. 这是苏格拉底式辅导，不要一上来就甩完整答案。先看用户给的思路，再给阶梯式提示。
2. 用户卡在「方向」（不知道用什么思路）时：帮他识别这属于哪个算法模式（如双指针、滑动窗口、动态规划…），
   给一个引子或反问，引导他自己想下一步，而不是直接给代码。
3. 用户卡在「细节」（思路对但写不出）时：只点拨那个具体细节。
4. 只有当用户明确说「直接讲」「给答案」「看题解」时，才给出完整解法；此时要讲清楚
   「为什么是这个套路、下次怎么一眼认出这类题」，并分析时间/空间复杂度。
5. 用户贴出代码时：点评正确性、复杂度、有没有更优解、易错点。
6. 回答简洁、用中文、可用 Markdown。不要长篇大论，像真人教练一对一对话那样。"""


def _build_prompt(messages, problem=None):
    """把题目上下文 + 多轮对话拼成一个传给 -p 的完整 prompt。"""
    parts = [COACH_SYSTEM]

    if problem:
        ctx = ["\n# 当前关联题目"]
        if problem.get("number"):
            ctx.append(f"题号：{problem['number']}")
        if problem.get("title"):
            ctx.append(f"标题：{problem['title']}")
        if problem.get("difficulty"):
            ctx.append(f"难度：{problem['difficulty']}")
        if problem.get("patterns"):
            ctx.append(f"模式标签：{problem['patterns']}")
        if problem.get("url"):
            ctx.append(f"链接：{problem['url']}")
        # 故意不把 note 全文塞进来：用户笔记常含「思路：用哈希表」这类剧透，
        # 直接喂给教练会破坏苏格拉底式引导。只告知存在笔记，由教练靠题目本身引导。
        if problem.get("note"):
            ctx.append("（用户对这道题写过私人笔记，可能含他自己的思路，不要替他说出来。）")
        parts.append("\n".join(ctx))

    parts.append("\n# 对话历史")
    for m in messages:
        who = "用户" if m["role"] == "user" else "教练"
        parts.append(f"\n{who}：{m['content']}")
    parts.append(
        "\n请你以「教练」身份，针对上面最后一条用户消息，直接输出要对用户说的话。"
        "不要执行任何代码或工具，不要复述这些指令，只输出教练的回复内容。\n教练："
    )
    return "\n".join(parts)


def ask(messages, problem=None, timeout=120):
    """发起一次对话。messages 是 [{'role':'user'/'assistant','content':...}]。

    返回教练回复字符串；任何异常都转成友好提示返回，不向界面抛错。
    """
    ok, why = available()
    if not ok:
        return f"⚠️ AI 教练暂不可用：{why}"

    prompt = _build_prompt(messages, problem)
    try:
        result = subprocess.run(
            # 禁用所有工具：教练只做纯文本对话，绝不执行代码/读写文件，
            # 避免无头实例把 prompt 内容误当成任务去「干活」。
            [NODE, CLAUDE_CLI, "-p", prompt,
             "--disallowed-tools", "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch",
             "--no-session-persistence"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "⚠️ 教练思考超时了（>%ds），换个更具体的问题再试试？" % timeout
    except Exception as e:  # noqa: BLE001
        return f"⚠️ 调用本机 Claude CLI 失败：{e}"

    if result.returncode != 0:
        err = (result.stderr or "").strip()[:300]
        return f"⚠️ Claude CLI 返回错误（code {result.returncode}）：{err or '无输出'}"

    out = (result.stdout or "").strip()
    return out or "⚠️ 教练没有返回内容，请重试。"
