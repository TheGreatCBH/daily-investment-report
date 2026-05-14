import json
import os
from pathlib import Path

# 注意：.env 已由 daily_report/__init__.py 在包导入时加载，这里只负责读取。

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "watchlist.json"
REPORTS_DIR = ROOT / "reports"
PROMPTS_DIR = ROOT / "prompts"

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]


def load_config():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data.get("watchlist", []), data.get("email", {})
