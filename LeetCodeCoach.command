#!/bin/bash
# 双击即可启动 LeetCode Coach
# 这个文件可以放在桌面，双击运行；关闭请在弹出的终端窗口按 Ctrl+C
cd "$HOME/leetcode-coach" || { echo "找不到 ~/leetcode-coach 目录"; exit 1; }
echo "🧠 正在启动 LeetCode Coach ..."
echo "浏览器会自动打开。用完想关闭：在本窗口按 Ctrl+C，然后关掉窗口即可。"
echo ""
exec ./.venv/bin/streamlit run app.py
