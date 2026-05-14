from datetime import datetime

from .chart import render_chart_png
from .formatting import fmt_change, fmt_price, nm, volume_badge


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
  * {{ margin:0; padding:0; box-sizing:border-box; }}

  body {{
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: #080c12;
    color: #e6e8ec;
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
    color: #e6e8ec;
    letter-spacing: 2px;
  }}
  .header .date {{
    font-size: .88rem;
    color: #565c67;
    margin-top: 6px;
    letter-spacing: 0.5px;
  }}
  .header .divider {{
    width: 40px;
    height: 2px;
    background: #c9a96e;
    margin: 14px auto 0;
    border-radius: 1px;
    opacity: 0.6;
  }}

  .section-title {{
    font-size: .95rem;
    font-weight: 700;
    margin: 28px 0 12px;
    letter-spacing: 3px;
    color: #8b919c;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: #1e2733;
  }}

  .overview-table {{
    background: #161c26;
    border-radius: 14px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border: 1px solid #1e2733;
    margin-bottom: 16px;
  }}
  .overview-table table {{ width: 100%; min-width: 520px; border-collapse: collapse; font-size: .88rem; }}
  .overview-table th {{
    background: #11161e;
    padding: 10px 6px;
    text-align: right;
    font-size: .74rem;
    font-weight: 600;
    color: #565c67;
    letter-spacing: 1px;
    white-space: nowrap;
    border-bottom: 1px solid #1e2733;
  }}
  .overview-table th:first-child {{ text-align: left; padding-left: 16px; }}
  .overview-table td {{
    padding: 10px 6px;
    text-align: right;
    border-bottom: 1px solid #1e2733;
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
    color: #e6e8ec;
  }}
  .overview-table .cn-name {{ font-size: .72rem; color: #565c67; display: block; font-family: inherit; }}
  .up {{ color: #00c853; font-weight: 600; }}
  .down {{ color: #ff3d4f; font-weight: 600; }}

  .highlight-card {{
    background: #161c26;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    border: 1px solid #1e2733;
    position: relative;
    transition: border-color .2s;
  }}
  .highlight-card.rank-1 {{ border-color: #c9a96e; box-shadow: 0 0 20px rgba(201,169,110,0.15); }}
  .highlight-card.rank-2 {{ border-color: #7c8aa0; }}
  .highlight-card .hl-title {{
    font-size: .96rem;
    font-weight: 600;
    color: #e6e8ec;
    margin-bottom: 5px;
    line-height: 1.4;
  }}
  .highlight-card .hl-summary {{
    font-size: .84rem;
    color: #8b919c;
    margin-bottom: 6px;
    line-height: 1.5;
  }}
  .highlight-card .hl-meta {{
    font-size: .74rem;
    color: #565c67;
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
  .hl-tag-macro {{ background: rgba(201,169,110,0.18); color: #c9a96e; }}
  .hl-tag-stock {{ background: rgba(100,140,200,0.18); color: #8ab4f8; }}

  .stock-card {{
    background: #161c26;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
    border: 1px solid #1e2733;
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
    color: #e6e8ec;
    letter-spacing: 0.5px;
  }}
  .stock-card .sc-name {{ font-size: .78rem; color: #565c67; margin-top: 1px; }}
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
    color: #8b919c;
    font-size: .82rem;
  }}
  .stock-card .sc-changes b {{ font-weight: 600; }}
  .stock-card .sc-info {{
    font-size: .76rem;
    color: #565c67;
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
    color: #565c67;
    text-align: center;
    letter-spacing: 1px;
  }}
  .stock-card .sc-news {{
    margin-top: 10px;
    border-top: 1px solid #1e2733;
    padding-top: 10px;
  }}
  .stock-card .sc-news-item {{
    font-size: .8rem;
    padding: 3px 0;
    color: #8b919c;
    line-height: 1.5;
  }}
  .sc-news-detail {{
    margin: 4px 0;
    cursor: pointer;
  }}
  .sc-news-detail summary {{
    font-size: .8rem;
    color: #8b919c;
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
    color: #c9a96e;
    transition: transform .2s;
    flex-shrink: 0;
  }}
  .sc-news-detail[open] summary::before {{
    transform: rotate(90deg);
  }}
  .sc-news-src {{
    font-size: .65rem;
    color: #565c67;
    white-space: nowrap;
    flex-shrink: 0;
  }}
  .sc-analysis {{
    font-size: .78rem;
    color: #b0b8c4;
    line-height: 1.7;
    padding: 8px 0 8px 18px;
    margin-top: 2px;
    border-left: 2px solid #1e2733;
  }}

  .footer {{
    text-align: center;
    font-size: .72rem;
    color: #565c67;
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
        return '<div class="highlight-card"><span style="color:#565c67">暂无重要新闻</span></div>'
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
    for d in all_data:
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
