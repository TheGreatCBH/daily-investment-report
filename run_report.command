#!/bin/bash
# 双击运行：手动触发一次每日投资简报生成（拉数据 → LLM → HTML → 通知 + 邮件）。
# 等价于 launchd 定时任务，只是由你手动点一下立即跑一次。
#
# 用法：在 Finder 里双击本文件即可（macOS 会用「终端」打开并运行）。
#   首次双击如提示「无法打开，因为它来自身份不明的开发者」，
#   右键 → 打开 一次即可永久信任；或在「系统设置 → 隐私与安全性」里点「仍要打开」。
#   也可把本文件拖到 Dock 或桌面做快捷入口。

cd "$(dirname "$0")" || exit 1

echo "▶ 正在生成每日投资简报…（拉行情/新闻 → LLM 处理 → 渲染 → 通知/邮件）"
echo ""

./.venv/bin/python3 fetch_report.py
status=$?

echo ""
if [ "$status" -eq 0 ]; then
  echo "✅ 完成。报告已写入 reports/ 目录，系统通知/邮件已发送。"
else
  echo "❌ 失败（退出码 $status），详见上方日志。"
fi

echo ""
echo "按回车键关闭此窗口…"
read -r _
