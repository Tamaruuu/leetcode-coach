#!/bin/bash
# 新电脑首次部署：重建虚拟环境 + 装依赖。只需跑一次。
# 用法：  cd leetcode-coach && ./setup.sh
set -e
cd "$(dirname "$0")"

echo "🧠 LeetCode Coach 安装程序"
echo ""

# 1. 找 python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 没找到 python3。请先装 Python 3.9+：https://www.python.org/downloads/"
  exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. 建虚拟环境（已存在则跳过）
if [ ! -d ".venv" ]; then
  echo "📦 创建虚拟环境 .venv ..."
  python3 -m venv .venv
else
  echo "📦 .venv 已存在，跳过创建。"
fi

# 3. 装依赖
echo "⬇️  安装依赖（streamlit + pandas）..."
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

echo ""
echo "🎉 安装完成！启动：  ./start.sh"
echo "   浏览器会自动打开 http://localhost:8600"
echo ""
echo "ℹ️  数据库 leetcode.db 会在首次启动时自动创建（空库）。"
echo "   题库（4350 题）需要时跑：  ./.venv/bin/python fetch_problems.py"
echo "   AI 教练需本机装 claude-code-internal CLI；没装则该页提示暂不可用，不影响其它功能。"
