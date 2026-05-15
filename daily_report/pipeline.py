import logging
import os
from datetime import datetime

from .config import REPORTS_DIR, load_config
from .i18n import t
from .market_data import fetch_macro_news, fetch_ticker
from .news_llm import process_news_with_llm, summarize_stock_news, translate_news_titles
from .notify import send_email, send_notification
from .render_html import generate_html
from .utils import retry

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    os.makedirs(REPORTS_DIR, exist_ok=True)

    watchlist, email_config = load_config()
    total = len(watchlist)
    logger.info("正在拉取 S&P 500 宏观新闻 + %d 只标的数据…", total)

    try:
        macro_news = retry(fetch_macro_news, label="宏观新闻")
        logger.info("  → 宏观新闻: OK (%d 条)", len(macro_news))
    except Exception as e:
        logger.warning("  → 宏观新闻: FAIL (%s)，以空列表继续", e)
        macro_news = []

    results = []
    for item in watchlist:
        sym = item["symbol"]
        try:
            data = retry(
                lambda s=sym, it=item: fetch_ticker(
                    s,
                    search_terms=it.get("search_terms"),
                    name=it.get("name"),
                ),
                label=sym,
            )
            results.append(data)
            logger.info("  → %s: OK (%s%s)", sym, data.get("currency_symbol", "$"), data["price"])
        except Exception as e:
            logger.warning("  → %s: FAIL (%s)", sym, e)

    if not results:
        logger.error("没有成功拉取到任何数据，退出。")
        return

    logger.info("正在用 DeepSeek 处理新闻（翻译、排序、摘要）…")
    llm_result = process_news_with_llm(macro_news, results)
    if llm_result:
        mh = len(llm_result.get("macro_highlights", []))
        sh = len(llm_result.get("stock_highlights", []))
        logger.info("  要闻精选: %d 条宏观 + %d 条个股", mh, sh)
    else:
        logger.warning("LLM 新闻处理失败，报告将不包含精选新闻")

    news_translations = translate_news_titles(results)
    logger.info("  标题翻译: %d 条", len(news_translations))

    news_analyses, irrelevant_titles = summarize_stock_news(results)
    removed = len(irrelevant_titles)
    extra = "，剔除不相关 %d 条" % removed if removed else ""
    logger.info("  新闻解读: %d 条%s", len(news_analyses), extra)
    if irrelevant_titles:
        for d in results:
            d["news"] = [n for n in d["news"] if n["title"] not in irrelevant_titles]

    html = generate_html(results, llm_result, news_translations, news_analyses)
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"daily_report_{today}.html"
    path = REPORTS_DIR / filename
    path.write_bytes(b"\xef\xbb\xbf" + html.encode("utf-8"))
    logger.info("报告已生成: %s", path)

    send_notification(t("notification_title"), t("notification_message", date=today))

    to = email_config.get("address", "")
    if to:
        send_email(to, f"{t('email_subject')} — {today}", html)

    return str(path)
