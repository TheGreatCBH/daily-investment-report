import base64
import io
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent
WATCHLIST_PATH = ROOT / "watchlist.json"
REPORTS_DIR = ROOT / "reports"

load_dotenv(ROOT / ".env")
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]


def render_chart_png(chart_dates, chart_closes, is_up):
    """用 matplotlib 生成走势图，返回 base64 PNG"""
    color = "#00c853" if is_up else "#ff3d4f"
    bg = "#161c26"

    fig, ax = plt.subplots(figsize=(6.6, 1.9), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    xs = list(range(len(chart_closes)))
    ax.plot(xs, chart_closes, color=color, linewidth=1.5, clip_on=False)
    ax.fill_between(xs, chart_closes, min(chart_closes), color=color, alpha=0.08, linewidth=0)

    n = len(chart_dates)
    step = max(1, n // 5)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([chart_dates[i] for i in range(0, n, step)], fontsize=7, color="#565c67")
    ax.tick_params(axis="x", length=0, pad=4)

    ax.yaxis.set_major_locator(ticker.MaxNLocator(4))
    ax.tick_params(axis="y", labelsize=7, colors="#565c67", length=0, pad=4)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"${v:.1f}"))

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1e2733", linewidth=0.5)

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=bg, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def load_config():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data.get("watchlist", []), data.get("email", {})


def search_news(term, max_results=5):
    """用 yfinance Search 搜索关键词新闻"""
    try:
        from yfinance import Search
        s = Search(term)
        raw = s.news[:max_results] if s.news else []
    except Exception:
        return []
    items = []
    for n in raw:
        c = n.get("content", n)
        pub_str = c.get("pubDate") or c.get("displayTime") or datetime.now().isoformat()
        pub_name = "Yahoo Finance"
        if isinstance(c.get("provider"), dict):
            name = c["provider"].get("displayName", "")
            if name and name != "-":
                pub_name = name
        link = ""
        curl = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
        if isinstance(curl, dict):
            link = curl.get("url", "")
        items.append({
            "title": c.get("title", "-"),
            "summary": c.get("summary", ""),
            "provider": {"displayName": pub_name},
            "pubDate": pub_str,
            "link": link,
            "canonicalUrl": curl,
        })
    return items


def fmt_change(val):
    if val is None:
        return ("-", "")
    sign = "+" if val >= 0 else ""
    cls = "up" if val >= 0 else "down"
    return (f"{sign}{val:.2f}%", cls)


def fmt_price(val):
    if val is None:
        return "-"
    return f"${val:.2f}"


def nm(val):
    if val is None:
        return "-"
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    return f"${val/1e9:.0f}B"


def volume_badge(vol, avg):
    if not vol or not avg or avg == 0:
        return ("-", "")
    r = vol / avg
    if r >= 1.5:
        return (f"{vol:,.0f} 放量 {r:.1f}x", "hot")
    elif r <= 0.5:
        return (f"{vol:,.0f} 缩量 {r:.1f}x", "cold")
    return (f"{vol:,.0f}", "")


def fetch_ticker(symbol, search_terms=None):
    t = yf.Ticker(symbol)
    info = t.info

    df_month = t.history(period="1mo")
    df_1d = t.history(period="1d", interval="5m")
    if df_1d.empty:
        df_1d = t.history(period="5d", interval="30m")
        if df_1d.empty:
            df_1d = df_month

    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    current = info.get("currentPrice") or info.get("regularMarketPrice")
    day_change = ((current - prev_close) / prev_close * 100) if current and prev_close else None

    if len(df_month) >= 2:
        week_close = df_month.iloc[-6]["Close"] if len(df_month) >= 6 else df_month.iloc[0]["Close"]
        week_change = (df_month.iloc[-1]["Close"] - week_close) / week_close * 100
        month_change = (df_month.iloc[-1]["Close"] - df_month.iloc[0]["Close"]) / df_month.iloc[0]["Close"] * 100
    else:
        week_change = month_change = None

    chart_type = "1d" if len(df_1d) > 10 else "fallback"
    chart_dates = [d.strftime("%H:%M") for d in df_1d.index]
    chart_closes = [round(v, 2) for v in df_1d["Close"].tolist()]

    raw_news = t.news if t.news else []

    # ETF/基金：只用关键词搜索新闻；个股：用 ticker 新闻
    if search_terms:
        extra_news = []
        seen_titles = set()
        for term in search_terms:
            for n in search_news(term, max_results=4):
                key = n.get("title", "")[:60]
                if key not in seen_titles:
                    seen_titles.add(key)
                    extra_news.append(n)
        raw_news = extra_news
    else:
        raw_news = list(raw_news)[:5]

    news_items = []
    seen_titles = set()
    max_age_days = 3 if datetime.now().weekday() == 0 else 1
    for n in raw_news:
        c = n.get("content", n)
        pub_str = c.get("pubDate") or c.get("displayTime", "")
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(pub_str)
            if (datetime.now(dt.tzinfo) - dt).days > max_age_days:
                continue
        except Exception:
            pass
        title_key = c.get("title", "")[:60]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        news_items.append({
            "title": c.get("title", "-"),
            "summary": c.get("summary", ""),
            "publisher": c.get("provider", {}).get("displayName", "-"),
            "published": pub_str,
        })

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName", symbol),
        "market": info.get("exchange", "-"),
        "price": current,
        "prev_close": prev_close,
        "day_change": day_change,
        "week_change": week_change,
        "month_change": month_change,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "volume": info.get("volume"),
        "avg_volume": info.get("averageVolume"),
        "chart_dates": chart_dates,
        "chart_closes": chart_closes,
        "chart_type": chart_type,
        "news": news_items,
    }


def fetch_macro_news():
    try:
        sp = yf.Ticker("^GSPC")
        raw = sp.news[:8] if sp.news else []
    except Exception:
        raw = []
    items = []
    for n in raw:
        c = n.get("content", n)
        pub_str = c.get("pubDate") or c.get("displayTime", "")
        items.append({
            "title": c.get("title", "-"),
            "summary": c.get("summary", ""),
            "publisher": c.get("provider", {}).get("displayName", ""),
            "published": pub_str,
        })
    return items


def process_news_with_llm(macro_news, all_data):
    all_items = []
    for n in macro_news:
        all_items.append({"type": "macro", "title": n["title"], "publisher": n["publisher"]})
    for d in all_data:
        for n in d["news"]:
            all_items.append({
                "type": "stock", "symbol": d["symbol"], "name": d["name"],
                "title": n["title"], "publisher": n["publisher"],
            })

    if not all_items:
        return {"highlights": [], "macro_news": []}

    items_json = json.dumps(all_items, ensure_ascii=False, indent=2)
    prompt = f"""你是一个专业的财经新闻编辑。以下是今天需要处理的所有新闻。

请完成以下任务：
1. 将每条新闻标题翻译成中文（保留原意，语言简洁有力）
2. 为每条新闻写一段详细的中文摘要（3-5句话，100-150字），说清楚事件的来龙去脉及其影响。务必提取原文中的具体数字（如财报数据、涨跌幅、金额、百分比等）；如果原文没提到具体数字则不用编造
3. 按照对股市/股价的重要性从高到低排序。评判标准：
   - 宏观政策（利率、关税、监管）> 行业重大事件 > 公司财报/重大公告 > 分析师观点 > 一般市场评论
   - 考虑对用户持仓的影响（用户关注：NVDA AAPL NVO LULU UNH IAU ZEB.TO）
4. 只保留你认为真正重要的新闻，可以丢弃无关紧要的（如无实质内容的评论、重复内容等）

请直接返回如下 JSON 格式，不要有其他内容：
```json
{{
  "macro_highlights": [
    {{
      "title_cn": "中文标题",
      "summary_cn": "一句中文摘要",
      "publisher": "来源",
      "rank": 1
    }}
  ],
  "stock_highlights": [
    {{
      "title_cn": "中文标题",
      "summary_cn": "一句中文摘要",
      "symbol": "NVDA",
      "publisher": "来源",
      "rank": 2
    }}
  ]
}}
```

新闻列表：
{items_json}

注意：
- macro_highlights 放宏观/大盘相关新闻
- stock_highlights 放个股相关新闻，每条带上对应的 symbol
- 两个列表合并后按重要性排序，rank 从 1 开始
- 总共保留 10-15 条最重要的新闻
- 只返回 JSON，不要其他内容"""

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=8192,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        print(f"  [WARN] DeepSeek API 调用失败: {e}")
        return None


def summarize_stock_news(all_data):
    """为每只股票的每条新闻生成详细中文解读，按股票批量调用。
    返回 (summaries_dict, irrelevant_titles_set)"""
    all_summaries = {}
    irrelevant_titles = set()
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    for d in all_data:
        if not d["news"]:
            continue
        items = []
        for n in d["news"]:
            items.append({"title": n["title"], "summary": n.get("summary", "")})

        items_json = json.dumps(items, ensure_ascii=False, indent=2)
        prompt = f"""你是资深财经分析师。以下是标注为 {d['symbol']}（{d['name']}）的新闻。

	第一步：判断每条新闻是否与 {d["name"]}（{d["symbol"]}）相关。{d.get("description", "")}
	  - 新闻标题中提到了该公司/基金名 → 相关
	  - 新闻讨论该行业/板块的趋势 → 相关
	  - 新闻完全无关（不同行业、不同公司、纯属顺带提及） → 不相关，analysis 填 "IRRELEVANT"
	第二步：仅对相关新闻写中文解读（200-300字）：
	  1. 先概括新闻内容
	  2. 再分析对股价影响（利好/利空/中性），区分短期和长期
新闻列表：
{items_json}

重要：返回 items 数组长度必须等于 {len(items)} 条，每条含 "title" 和 "analysis" 字段。

返回 JSON 格式：
```json
{{
  "items": [
    {{"title": "原标题", "analysis": "中文解读内容"}}
  ]
}}
```
只返回 JSON，不要其他内容。"""

        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=4096,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.choices[0].message.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            for item in data.get("items", []):
                title = item.get("title", "")
                analysis = (item.get("analysis") or item.get("summary_cn") or
                           item.get("content") or item.get("解读") or item.get("text") or "")
                if analysis and "IRRELEVANT" in analysis.upper():
                    # 关键词兜底：ETF 标的搜索结果含底层资产关键词 → 强制保留
                    keep_by_kw = False
                    if d.get("search_terms"):
                        title_lower = title.lower()
                        asset_kw = {"gold", "mining", "bullion", "precious", "bank", "canadian",
                                     "tsx", "financial", "bmo", "rbc", "td", "scotiabank",
                                     "cibc", "wealth", "asset", "etf"}
                        keep_by_kw = any(kw in title_lower for kw in asset_kw)
                    if not keep_by_kw:
                        irrelevant_titles.add(title)
                        continue
                    # 关键词命中：强制保留，给个简短替代文案
                    analysis = "暂无详细解读"
                if title and analysis:
                    all_summaries[title] = analysis
                elif title:
                    all_summaries[title] = "暂无详细解读"
        except Exception as e:
            print(f"    {d['symbol']} 新闻解读失败: {e}")

    return all_summaries, irrelevant_titles


def translate_news_titles(all_data):
    """批量翻译个股新闻标题为中文"""
    # 收集所有需翻译的标题
    titles_map = {}
    for d in all_data:
        for n in d["news"]:
            key = f"{d['symbol']}::{n['title'][:100]}"
            titles_map[key] = n["title"]

    if not titles_map:
        return {}

    titles_list = "\n".join([f"- {v}" for v in titles_map.values()])
    prompt = f"""将以下英文新闻标题翻译成中文，保持简洁有力。返回 JSON 格式：

```json
{{
  "translations": [
    {{"original": "原文", "translated": "译文"}}
  ]
}}
```

{titles_list}"""

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=2048,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        data = json.loads(text.strip())
        return {t["original"]: t["translated"] for t in data.get("translations", [])}
    except Exception as e:
        print(f"失败: {e}")
        return {}


def parse_date_str(s):
    if not s:
        return "-"
    try:
        from dateutil import parser as date_parser
        dt = date_parser.parse(s)
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return s


def generate_html(all_data, llm_result, news_translations=None, news_analyses=None):
    if news_translations is None:
        news_translations = {}
    if news_analyses is None:
        news_analyses = {}
    today = datetime.now().strftime("%Y-%m-%d")
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    macro_highlights = llm_result.get("macro_highlights", []) if llm_result else []
    stock_highlights = llm_result.get("stock_highlights", []) if llm_result else []
    all_highlights = sorted(macro_highlights + stock_highlights, key=lambda x: x.get("rank", 99))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日投资简报 — {today}</title>
<style>
  :root {{
    --bg: #080c12;
    --surface: #11161e;
    --card: #161c26;
    --card-hover: #1b2230;
    --text: #e6e8ec;
    --text-secondary: #8b919c;
    --text-dim: #565c67;
    --up: #00c853;
    --up-bg: rgba(0,200,83,0.08);
    --up-glow: rgba(0,200,83,0.15);
    --down: #ff3d4f;
    --down-bg: rgba(255,61,79,0.08);
    --down-glow: rgba(255,61,79,0.12);
    --accent: #c9a96e;
    --accent-dim: rgba(201,169,110,0.15);
    --border: #1e2733;
    --border-light: #263040;
    --radius: 14px;
    --radius-sm: 10px;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}

  body {{
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 14px 10px;
    -webkit-font-smoothing: antialiased;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(201,169,110,0.04) 0%, transparent 55%),
      radial-gradient(ellipse at 80% 100%, rgba(0,200,83,0.03) 0%, transparent 55%);
  }}
  .container {{ max-width: 680px; margin: 0 auto; }}

  .header {{
    text-align: center;
    padding: 18px 0 24px;
  }}
  .header h1 {{
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: 2px;
  }}
  .header .date {{
    font-size: .88rem;
    color: var(--text-dim);
    margin-top: 6px;
    letter-spacing: 0.5px;
  }}
  .header .divider {{
    width: 40px;
    height: 2px;
    background: var(--accent);
    margin: 14px auto 0;
    border-radius: 1px;
    opacity: 0.6;
  }}

  .section-title {{
    font-size: .95rem;
    font-weight: 700;
    margin: 28px 0 12px;
    letter-spacing: 3px;
    color: var(--text-secondary);
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }}

  .overview-table {{
    background: var(--card);
    border-radius: var(--radius);
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border: 1px solid var(--border);
    margin-bottom: 16px;
  }}
  .overview-table table {{ width: 100%; min-width: 520px; border-collapse: collapse; font-size: .88rem; }}
  .overview-table th {{
    background: var(--surface);
    padding: 10px 6px;
    text-align: right;
    font-size: .74rem;
    font-weight: 600;
    color: var(--text-dim);
    letter-spacing: 1px;
    white-space: nowrap;
    border-bottom: 1px solid var(--border);
  }}
  .overview-table th:first-child {{ text-align: left; padding-left: 16px; }}
  .overview-table td {{
    padding: 10px 6px;
    text-align: right;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", "Consolas", monospace;
    font-size: .84rem;
  }}
  .overview-table tr:last-child td {{ border-bottom: none; }}
  .overview-table td:first-child {{ text-align: left; padding-left: 16px; font-family: inherit; }}
  .overview-table .sym {{
    font-weight: 700;
    font-size: .9rem;
    font-family: inherit;
    color: var(--text);
  }}
  .overview-table .cn-name {{ font-size: .72rem; color: var(--text-dim); display: block; font-family: inherit; }}
  .up {{ color: var(--up); font-weight: 600; }}
  .down {{ color: var(--down); font-weight: 600; }}

  .highlight-card {{
    background: var(--card);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    margin-bottom: 8px;
    border: 1px solid var(--border);
    position: relative;
    transition: border-color .2s;
  }}
  .highlight-card.rank-1 {{ border-color: var(--accent); box-shadow: 0 0 20px var(--accent-dim); }}
  .highlight-card.rank-2 {{ border-color: #7c8aa0; }}
  .highlight-card .hl-title {{
    font-size: .96rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 5px;
    line-height: 1.4;
  }}
  .highlight-card .hl-summary {{
    font-size: .84rem;
    color: var(--text-secondary);
    margin-bottom: 6px;
    line-height: 1.5;
  }}
  .highlight-card .hl-meta {{
    font-size: .74rem;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .highlight-card .hl-tag {{
    display: inline-flex;
    align-items: center;
    font-size: .7rem;
    padding: 2px 8px;
    border-radius: 4px;
    margin-right: 6px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }}
  .hl-tag-macro {{ background: rgba(201,169,110,0.18); color: var(--accent); }}
  .hl-tag-stock {{ background: rgba(100,140,200,0.18); color: #8ab4f8; }}

  .stock-card {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 18px;
    margin-bottom: 16px;
    border: 1px solid var(--border);
  }}
  .stock-card .sc-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
  }}
  .stock-card .sc-symbol {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: 0.5px;
  }}
  .stock-card .sc-name {{ font-size: .78rem; color: var(--text-dim); margin-top: 1px; }}
  .stock-card .sc-price {{
    font-size: 1.45rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
  }}
  .stock-card .sc-changes {{
    display: flex;
    gap: 16px;
    font-size: .86rem;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }}
  .stock-card .sc-changes span {{
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
    font-variant-numeric: tabular-nums;
    color: var(--text-secondary);
    font-size: .82rem;
  }}
  .stock-card .sc-changes b {{ font-weight: 600; }}
  .stock-card .sc-info {{
    font-size: .76rem;
    color: var(--text-dim);
    margin-bottom: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
  }}
  .stock-card .chart-wrap {{
    margin: 12px 0 4px;
    width: 100%;
  }}
  .stock-card .chart-wrap img {{
    width: 100%;
    height: auto;
    display: block;
    border-radius: 6px;
  }}
  .stock-card .chart-label {{
    font-size: .7rem;
    color: var(--text-dim);
    text-align: center;
    letter-spacing: 1px;
  }}
  .stock-card .sc-news {{
    margin-top: 10px;
    border-top: 1px solid var(--border);
    padding-top: 10px;
  }}
  .stock-card .sc-news-item {{
    font-size: .8rem;
    padding: 3px 0;
    color: var(--text-secondary);
    line-height: 1.5;
  }}
  .sc-news-detail {{
    margin: 4px 0;
    cursor: pointer;
  }}
  .sc-news-detail summary {{
    font-size: .8rem;
    color: var(--text-secondary);
    padding: 4px 0;
    outline: none;
    list-style: none;
    display: flex;
    align-items: baseline;
    gap: 8px;
    cursor: pointer;
  }}
  .sc-news-detail summary::-webkit-details-marker {{ display: none; }}
  .sc-news-detail summary::before {{
    content: '▸';
    display: inline-block;
    font-size: .7rem;
    color: var(--accent);
    transition: transform .2s;
    flex-shrink: 0;
  }}
  .sc-news-detail[open] summary::before {{
    transform: rotate(90deg);
  }}
  .sc-news-src {{
    font-size: .65rem;
    color: var(--text-dim);
    white-space: nowrap;
    flex-shrink: 0;
  }}
  .sc-analysis {{
    font-size: .78rem;
    color: #b0b8c4;
    line-height: 1.7;
    padding: 8px 0 8px 18px;
    margin-top: 2px;
    border-left: 2px solid var(--border);
  }}

  .footer {{
    text-align: center;
    font-size: .72rem;
    color: var(--text-dim);
    margin-top: 24px;
    padding-bottom: 28px;
    letter-spacing: 0.5px;
    opacity: 0.6;
  }}

  @media (max-width: 480px) {{
    body {{ padding: 8px 4px; }}
    .header h1 {{ font-size: 1.25rem; letter-spacing: 1px; }}
    .stock-card {{ padding: 14px; }}
    .overview-table td, .overview-table th {{ padding: 7px 4px; font-size: .68rem; }}
    .overview-table .sym {{ font-size: .74rem; }}
    .overview-table .cn-name {{ font-size: .62rem; }}
    .highlight-card {{ padding: 12px; }}
  }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>每日投资简报</h1>
  <div class="date">{today}</div>
  <div class="divider"></div>
</div>

<div class="section-title">今日要闻</div>

{_render_highlights(all_highlights)}

<div class="section-title">持仓概览</div>

{_render_overview(all_data)}

{_render_stock_cards(all_data, news_translations, news_analyses)}

<div class="footer">
  {gen_time} &middot; Yahoo Finance &middot; DeepSeek AI 摘要
</div>

</div>

</body>
</html>"""


def _render_highlights(highlights):
    if not highlights:
        return '<div class="highlight-card"><span style="color:var(--text-dim)">暂无重要新闻</span></div>'
    items = []
    for h in highlights:
        rank = h.get("rank", 99)
        cls = f"rank-{min(rank, 2)}"
        is_macro = "macro" in h.get("type", "") or h.get("type") == "macro" or "symbol" not in h
        tag_html = '<span class="hl-tag hl-tag-macro">宏观</span>' if is_macro else f'<span class="hl-tag hl-tag-stock">{h.get("symbol", "")}</span>'
        items.append(f"""<div class="highlight-card {cls}">
  <div class="hl-title">{tag_html}{h.get("title_cn", h.get("title", "-"))}</div>
  <div class="hl-summary">{h.get("summary_cn", "")}</div>
  <div class="hl-meta">{h.get("publisher", "")}</div>
</div>""")
    return "\n".join(items)


def _render_overview(all_data):
    rows = []
    for d in all_data:
        dc, dc_cls = fmt_change(d["day_change"])
        wc, wc_cls = fmt_change(d["week_change"])
        mc, mc_cls = fmt_change(d["month_change"])
        rows.append(
            f"""<tr>
              <td><span class="sym">{d['symbol']}</span><span class="cn-name">{d['name']}</span></td>
              <td>{fmt_price(d['price'])}</td>
              <td class="{dc_cls}">{dc}</td>
              <td class="{wc_cls}">{wc}</td>
              <td class="{mc_cls}">{mc}</td>
              <td>{nm(d['market_cap'])}</td>
            </tr>"""
        )
    return f"""<div class="overview-table">
    <table>
      <thead><tr>
        <th>代码</th><th>现价</th><th>日涨跌</th><th>周涨跌</th><th>月涨跌</th><th>市值</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>"""


def _render_stock_cards(all_data, news_translations=None, news_analyses=None):
    if news_translations is None:
        news_translations = {}
    if news_analyses is None:
        news_analyses = {}
    cards = []
    for i, d in enumerate(all_data):
        dc, dc_cls = fmt_change(d["day_change"])
        wc, wc_cls = fmt_change(d["week_change"])
        mc, mc_cls = fmt_change(d["month_change"])
        vol_str, vol_cls = volume_badge(d["volume"], d["avg_volume"])

        news_html = ""
        if d["news"]:
            items = []
            for n in d["news"][:3]:
                title = news_translations.get(n["title"], n["title"])
                analysis = news_analyses.get(n["title"], "")
                if analysis:
                    items.append(f'''<details class="sc-news-detail">
  <summary>{title} <span class="sc-news-src">{n["publisher"]}</span></summary>
  <div class="sc-analysis">{analysis}</div>
</details>''')
                else:
                    items.append(f'<div class="sc-news-item">&mdash; {title} <span class="sc-news-src">{n["publisher"]}</span></div>')
            news_html = '<div class="sc-news">' + "".join(items) + "</div>"

        chart_hint = "日内走势" if d["chart_type"] == "1d" else "近期走势"
        is_up = (d.get("month_change") or 0) >= 0
        chart_b64 = render_chart_png(d["chart_dates"], d["chart_closes"], is_up)

        cards.append(f"""<div class="stock-card">
  <div class="sc-header">
    <div>
      <div class="sc-symbol">{d['symbol']}</div>
      <div class="sc-name">{d['name']} &middot; {d['market']}</div>
    </div>
    <div class="sc-price">{fmt_price(d['price'])}</div>
  </div>
  <div class="sc-changes">
    <span>日 <b class="{dc_cls}">{dc}</b></span>
    <span>周 <b class="{wc_cls}">{wc}</b></span>
    <span>月 <b class="{mc_cls}">{mc}</b></span>
  </div>
  <div class="sc-info">
    <span>市值 {nm(d['market_cap'])}</span>
    <span>PE {d['pe_ratio'] or '-'}</span>
    <span>52w高 {fmt_price(d['high_52w'])}</span>
    <span>52w低 {fmt_price(d['low_52w'])}</span>
    <span>量 {vol_str}</span>
  </div>
  <div class="chart-wrap">
    <img src="data:image/png;base64,{chart_b64}" alt="{d['symbol']}走势图" />
  </div>
  <div class="chart-label">{chart_hint}</div>
  {news_html}
</div>""")
    return "\n".join(cards)


def send_notification(title, message):
    """macOS 系统通知"""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "Glass"'
        ], check=True)
        print(f"  通知已发送")
    except Exception as e:
        print(f"  [WARN] 通知发送失败: {e}")


def send_email(to, subject, html_content, email_config, report_path):
    """通过 Mail.app 发送报告（HTML 作为附件）"""
    subject_escaped = subject.replace('"', '\\"')
    report_escaped = str(report_path.absolute()).replace('"', '\\"')

    applescript = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject_escaped}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to}"}}
            set content to "今日投资简报已生成，请下载附件后用浏览器打开查看完整报告（含走势图）。"
            make new attachment with properties {{file name:POSIX file "{report_escaped}"}} at after last paragraph
            send
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", applescript], check=True, timeout=30)
        print(f"  邮件已发送至 {to}")
    except Exception as e:
        print(f"  [WARN] 邮件发送失败: {e}")


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

    llm_result = None
    print("\n正在用 DeepSeek 处理新闻（翻译、排序、摘要）…")
    llm_result = process_news_with_llm(macro_news, results)
    if llm_result:
        mh = len(llm_result.get("macro_highlights", []))
        sh = len(llm_result.get("stock_highlights", []))
        print(f"  OK: {mh} 条宏观 + {sh} 条个股精选")
    else:
        print("[WARN] LLM 新闻处理失败，报告将不包含精选新闻")

    # 翻译个股底部新闻标题
    print("  翻译个股新闻标题…", end=" ")
    news_translations = translate_news_titles(results)
    if news_translations:
        print(f"OK ({len(news_translations)} 条)")
    else:
        print("跳过")

    # 为每只股票的新闻生成详细解读
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
    path.write_bytes(b'\xef\xbb\xbf' + html.encode("utf-8"))

    print(f"\n报告已生成: {path}")

    send_notification("每日投资简报", f"{today} 报告已生成")

    to = email_config.get("address", "")
    if to:
        send_email(to, f"每日投资简报 — {today}", html, email_config, path)

    return str(path)


if __name__ == "__main__":
    main()
