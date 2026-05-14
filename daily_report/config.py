import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "watchlist.json"
REPORTS_DIR = ROOT / "reports"
PROMPTS_DIR = ROOT / "prompts"

load_dotenv(ROOT / ".env")

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]


def load_config():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data.get("watchlist", []), data.get("email", {})
