"""保留为 cron 入口（向后兼容）。实际实现在 daily_report 包里。"""
from daily_report.pipeline import main

if __name__ == "__main__":
    main()
