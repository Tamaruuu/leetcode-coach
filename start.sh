#!/bin/bash
# 一键启动 LeetCode Coach
cd "$(dirname "$0")"
./.venv/bin/streamlit run app.py
