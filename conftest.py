import os
import sys

# 将项目根目录加入 sys.path，使 tests/ 下的测试可以直接 import daily_report
sys.path.insert(0, os.path.dirname(__file__))

# 确保 config.py 模块级代码在无 .env 时仍能通过
os.environ.setdefault("LLM_API_KEY", "test-key")
