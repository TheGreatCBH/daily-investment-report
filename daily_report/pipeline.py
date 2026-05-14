import os
from datetime import datetime

from .config import REPORTS_DIR, load_config
from .market_data import fetch_macro_news, fetch_ticker
from .news_llm import process_news_with_llm, summarize_stock_news, translate_news_titles
from .notify import send_email, send_notification
from .render_html import generate_html


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)

    watchlist, email_config = load_config()
    total = len(watchlist)
    print(f"正在拉取 S&P 500 宏观新闻 + {total} 只标的数据…")

    print("  → 宏观新闻 …", end=" ")
    macro_news = fetch_macro_news()
    print(f"OK ({len(macro_news)} 条)")

    results = []
    for item in watchlist:
        sym = item["symbol"]
        try:
            print(f"  → {sym} …", end=" ")
            terms = item.get("search_terms")
            data = fetch_ticker(sym, search_terms=terms)
            results.append(data)
            print(f"OK (${data['price']})")
        except Exception as e:
            print(f"FAIL: {e}")

    if not results:
        print("没有成功拉取到任何数据，退出。")
        return

    print("\n正在用 DeepSeek 处理新闻（翻译、排序、摘要）…")
    llm_result = process_news_with_llm(macro_news, results)
    if llm_result:
        mh = len(llm_result.get("macro_highlights", []))
        sh = len(llm_result.get("stock_highlights", []))
        print(f"  OK: {mh} 条宏观 + {sh} 条个股精选")
    else:
        print("[WARN] LLM 新闻处理失败，报告将不包含精选新闻")

    print("  翻译个股新闻标题…", end=" ")
    news_translations = translate_news_titles(results)
    if news_translations:
        print(f"OK ({len(news_translations)} 条)")
    else:
        print("跳过")

    print("  生成新闻详细解读…")
    news_analyses, irrelevant_titles = summarize_stock_news(results)
    if news_analyses:
        removed = len(irrelevant_titles)
        extra = f"，剔除了 {removed} 条不相关" if removed else ""
        print(f"  OK ({len(news_analyses)} 条解读{extra})")
        if irrelevant_titles:
            for d in results:
                d["news"] = [n for n in d["news"] if n["title"] not in irrelevant_titles]
    else:
        print("  跳过")

    html = generate_html(results, llm_result, news_translations, news_analyses)
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"daily_report_{today}.html"
    path = REPORTS_DIR / filename
    path.write_bytes(b"\xef\xbb\xbf" + html.encode("utf-8"))

    print(f"\n报告已生成: {path}")

    send_notification("每日投资简报", f"{today} 报告已生成")

    to = email_config.get("address", "")
    if to:
        send_email(to, f"每日投资简报 — {today}", html, email_config, path)

    return str(path)
