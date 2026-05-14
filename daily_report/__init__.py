"""daily_report: 自动化每日投资简报的核心包。

包级别一次性加载 .env，让任意子模块（包括独立测试 / 第三方集成）都能直接读到环境变量。
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
