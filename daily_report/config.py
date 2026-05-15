import json
import os
from pathlib import Path

# 注意：.env 已由 daily_report/__init__.py 在包导入时加载，这里只负责读取。

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "watchlist.json"
REPORTS_DIR = ROOT / "reports"
PROMPTS_DIR = ROOT / "prompts"

# LLM 配置：支持任何 OpenAI 兼容接口（OpenAI / DeepSeek / Groq / Ollama 等）
# LLM_API_KEY 优先；DEEPSEEK_API_KEY 保留作向后兼容兜底
_llm_key = os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
if not _llm_key:
    raise RuntimeError(
        "LLM API key is not set.\n"
        "  1. Copy .env.example to .env\n"
        "  2. Set LLM_API_KEY=<your-key> in .env\n"
        "  DeepSeek: https://platform.deepseek.com\n"
        "  OpenAI:   https://platform.openai.com"
    )
LLM_API_KEY = _llm_key

# 显式设为空字符串（LLM_BASE_URL=）→ 使用 OpenAI 官方端点（适合 openai 直连）
# 不设置 → 默认 DeepSeek，保持向后兼容；其他服务商按文档填写
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")

# 对应服务商的模型 ID
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")


def load_config():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data.get("watchlist", []), data.get("email", {})
