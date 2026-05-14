"""轻量级 i18n：通过环境变量 REPORT_LOCALE 切换报告语言。

默认 zh-CN（与项目长期默认行为一致）。支持 en-US。
所有面向用户可见的 HTML/邮件/通知字面量都通过 t() 取值；
prompts 用文件级 i18n（prompts/en/ 镜像），由 news_llm 选择加载路径。
"""
import os

LOCALE = os.environ.get("REPORT_LOCALE", "zh-CN")

_STRINGS = {
    "zh-CN": {
        # 报头 / 段标题
        "title": "每日投资简报",
        "section_highlights": "今日要闻",
        "section_overview": "持仓概览",

        # 持仓概览表头
        "th_symbol": "代码",
        "th_price": "现价",
        "th_day": "日涨跌",
        "th_week": "周涨跌",
        "th_month": "月涨跌",
        "th_market_cap": "市值",

        # 个股卡片
        "tag_macro": "宏观",
        "no_highlights": "暂无重要新闻",
        "label_day": "日",
        "label_week": "周",
        "label_month": "月",
        "label_market_cap": "市值",
        "label_pe": "PE",
        "label_52w_high": "52w高",
        "label_52w_low": "52w低",
        "label_volume": "量",
        "chart_intraday": "日内走势",
        "chart_recent": "近期走势",

        # 成交量 badge
        "high_volume": "放量",
        "low_volume": "缩量",

        # A 股市场标签
        "market_sh": "上交所",
        "market_sz": "深交所",

        # 页脚
        "footer_credit": "Yahoo Finance · DeepSeek AI 摘要",

        # 邮件 / 通知
        "email_subject": "每日投资简报",
        "notification_title": "每日投资简报",
        "notification_message": "{date} 报告已生成",
    },
    "en-US": {
        "title": "Daily Investment Brief",
        "section_highlights": "Today's Highlights",
        "section_overview": "Portfolio Overview",

        "th_symbol": "Symbol",
        "th_price": "Price",
        "th_day": "Day",
        "th_week": "Week",
        "th_month": "Month",
        "th_market_cap": "Market Cap",

        "tag_macro": "Macro",
        "no_highlights": "No significant news today",
        "label_day": "D",
        "label_week": "W",
        "label_month": "M",
        "label_market_cap": "Cap",
        "label_pe": "P/E",
        "label_52w_high": "52w High",
        "label_52w_low": "52w Low",
        "label_volume": "Vol",
        "chart_intraday": "Intraday",
        "chart_recent": "Recent trend",

        "high_volume": "high vol",
        "low_volume": "low vol",

        "market_sh": "Shanghai",
        "market_sz": "Shenzhen",

        "footer_credit": "Yahoo Finance · DeepSeek AI Summary",

        "email_subject": "Daily Investment Brief",
        "notification_title": "Daily Investment Brief",
        "notification_message": "Report for {date} generated",
    },
}


def t(key, **kwargs):
    """取当前 locale 下的字符串，如果当前 locale 缺该 key 则 fall back 到 zh-CN。
    支持 .format() 占位符（用 kwargs 传入）。"""
    table = _STRINGS.get(LOCALE, _STRINGS["zh-CN"])
    value = table.get(key) or _STRINGS["zh-CN"].get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value
