from datetime import datetime

from .chart import render_chart_png
from .formatting import fmt_change, fmt_price, nm, volume_badge
from .i18n import LOCALE, t


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
<html lang="{LOCALE}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t("title")} — {today}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}

  body {{
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: #f4f6f9;
    color: #15181e;
    line-height: 1.6;
    padding: 14px 10px;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 680px; margin: 0 auto; }}

  .header {{ text-align: center; padding: 18px 0 24px; }}
  .header h1 {{
    font-size: 1.45rem;
    font-weight: 700;
    color: #15181e;
    letter-spacing: 2px;
  }}
  .header .date {{
    font-size: .88rem;
    color: #9298a3;
    margin-top: 6px;
    letter-spacing: 0.5px;
  }}
  .header .divider {{
    width: 40px;
    height: 2px;
    background: #c9a96e;
    margin: 14px auto 0;
    border-radius: 1px;
    opacity: 0.8;
  }}

  .section-title {{
    font-size: .95rem;
    font-weight: 700;
    margin: 28px 0 12px;
    letter-spacing: 3px;
    color: #5a606b;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: #e0e5ec;
  }}

  .overview-table {{
    background: #ffffff;
    border-radius: 14px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border: 1px solid #e0e5ec;
    margin-bottom: 16px;
  }}
  .overview-table table {{ width: 100%; min-width: 520px; border-collapse: collapse; font-size: .88rem; }}
  .overview-table th {{
    background: #edf0f5;
    padding: 10px 6px;
    text-align: right;
    font-size: .74rem;
    font-weight: 600;
    color: #9298a3;
    letter-spacing: 1px;
    white-space: nowrap;
    border-bottom: 1px solid #e0e5ec;
  }}
  .overview-table th:first-child {{ text-align: left; padding-left: 16px; }}
  /* 不要在这里设 color —— 让 .up/.down 通过继承生效 */
  .overview-table td {{
    padding: 10px 6px;
    text-align: right;
    border-bottom: 1px solid #e0e5ec;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", "Consolas", monospace;
    font-size: .84rem;
  }}
  .overview-table tr:last-child td {{ border-bottom: none; }}
  .overview-table td:first-child {{ text-align: left; padding-left: 16px; font-family: inherit; }}
  .overview-table .sym {{ font-weight: 700; font-size: .9rem; font-family: inherit; color: #15181e; }}
  .overview-table .cn-name {{ font-size: .72rem; color: #9298a3; display: block; font-family: inherit; }}
  .up {{ color: #0d9550; font-weight: 600; }}
  .down {{ color: #dc2c3a; font-weight: 600; }}

  .highlight-card {{
    background: #ffffff;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    border: 1px solid #e0e5ec;
    position: relative;
  }}
  .highlight-card.rank-1 {{
    border-color: #c9a96e;
    box-shadow: 0 0 0 1px rgba(201,169,110,0.18), 0 4px 16px rgba(201,169,110,0.18);
  }}
  .highlight-card.rank-2 {{ border-color: #c0c6d0; }}
  .highlight-card .hl-title {{
    font-size: .96rem;
    font-weight: 600;
    color: #15181e;
    margin-bottom: 5px;
    line-height: 1.4;
  }}
  .highlight-card .hl-summary {{
    font-size: .84rem;
    color: #5a606b;
    margin-bottom: 6px;
    line-height: 1.5;
  }}
  .highlight-card .hl-meta {{
    font-size: .74rem;
    color: #9298a3;
  }}
  .highlight-card .hl-tag {{
    display: inline-block;
    font-size: .7rem;
    padding: 2px 8px;
    border-radius: 4px;
    margin-right: 6px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }}
  .hl-tag-macro {{ background: rgba(201,169,110,0.18); color: #8a6d2a; }}
  .hl-tag-stock {{ background: rgba(70,110,180,0.13); color: #2e5cb8; }}

  .stock-card {{
    background: #ffffff;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
    border: 1px solid #e0e5ec;
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
    color: #15181e;
    letter-spacing: 0.5px;
  }}
  .stock-card .sc-name {{ font-size: .78rem; color: #9298a3; margin-top: 1px; }}
  .stock-card .sc-price {{
    font-size: 1.45rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
    color: #15181e;
  }}
  /* inline-block + margin 替代 flex gap：iOS Outlook 不支持 gap 属性 */
  .stock-card .sc-changes {{
    font-size: .86rem;
    margin-bottom: 10px;
    line-height: 1.8;
  }}
  .stock-card .sc-changes span {{
    display: inline-block;
    margin-right: 18px;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
    font-variant-numeric: tabular-nums;
    color: #5a606b;
    font-size: .82rem;
  }}
  .stock-card .sc-changes b {{ font-weight: 600; }}
  .stock-card .sc-info {{
    font-size: .76rem;
    color: #9298a3;
    margin-bottom: 4px;
    line-height: 1.8;
  }}
  .stock-card .sc-info span {{
    display: inline-block;
    margin-right: 16px;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
  }}
  .stock-card .chart-wrap {{ margin: 12px 0 4px; width: 100%; }}
  .stock-card .chart-wrap img {{
    width: 100%;
    height: auto;
    display: block;
    border-radius: 6px;
  }}
  .stock-card .chart-label {{
    font-size: .7rem;
    color: #9298a3;
    text-align: center;
    letter-spacing: 1px;
  }}
  .stock-card .sc-news {{
    margin-top: 10px;
    border-top: 1px solid #e0e5ec;
    padding-top: 10px;
  }}
  .sc-news-item {{
    margin: 4px 0;
    padding: 6px 0;
  }}
  .sc-news-title {{
    font-size: .82rem;
    color: #15181e;
    font-weight: 500;
    line-height: 1.5;
  }}
  .sc-news-title::before {{
    content: '·';
    color: #c9a96e;
    font-weight: 700;
    margin-right: 6px;
  }}
  .sc-news-src {{
    font-size: .65rem;
    color: #9298a3;
    margin-left: 8px;
    letter-spacing: 0.04em;
  }}
  .sc-analysis {{
    font-size: .78rem;
    color: #5a606b;
    line-height: 1.7;
    padding: 6px 0 4px 12px;
    margin-top: 4px;
    border-left: 2px solid #c9a96e;
  }}

  .footer {{
    text-align: center;
    font-size: .72rem;
    color: #9298a3;
    margin-top: 24px;
    padding-bottom: 28px;
    letter-spacing: 0.5px;
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
  <h1>{t("title")}</h1>
  <div class="date">{today}</div>
  <div class="divider"></div>
</div>

<div class="section-title">{t("section_highlights")}</div>

{_render_highlights(all_highlights)}

<div class="section-title">{t("section_overview")}</div>

{_render_overview(all_data)}

{_render_stock_cards(all_data, news_translations, news_analyses)}

<div class="footer">
  {gen_time} &middot; {t("footer_credit")}
</div>

</div>

</body>
</html>"""


def _render_highlights(highlights):
    if not highlights:
        return f'<div class="highlight-card"><span style="color:#9298a3">{t("no_highlights")}</span></div>'
    items = []
    for h in highlights:
        rank = h.get("rank", 99)
        cls = f"rank-{min(rank, 2)}"
        is_macro = "macro" in h.get("type", "") or h.get("type") == "macro" or "symbol" not in h
        tag_html = f'<span class="hl-tag hl-tag-macro">{t("tag_macro")}</span>' if is_macro else f'<span class="hl-tag hl-tag-stock">{h.get("symbol", "")}</span>'
        items.append(f"""<div class="highlight-card {cls}">
  <div class="hl-title">{tag_html}{h.get("title_cn", h.get("title", "-"))}</div>
  <div class="hl-summary">{h.get("summary_cn", "")}</div>
  <div class="hl-meta">{h.get("publisher", "")}</div>
</div>""")
    return "\n".join(items)


def _primary_secondary(d):
    """A/H 股（纯数字代号）以名称为主、代号为副；美股/加股反之。"""
    sym = d["symbol"]
    name = d["name"]
    if sym.endswith((".SS", ".SZ", ".HK")):
        return name, sym
    return sym, name


def _render_overview(all_data):
    rows = []
    for d in all_data:
        cur = d.get("currency_symbol", "$")
        primary, secondary = _primary_secondary(d)
        dc, dc_cls = fmt_change(d["day_change"])
        wc, wc_cls = fmt_change(d["week_change"])
        mc, mc_cls = fmt_change(d["month_change"])
        rows.append(
            f"""<tr>
              <td><span class="sym">{primary}</span><span class="cn-name">{secondary}</span></td>
              <td>{fmt_price(d['price'], cur)}</td>
              <td class="{dc_cls}">{dc}</td>
              <td class="{wc_cls}">{wc}</td>
              <td class="{mc_cls}">{mc}</td>
              <td>{nm(d['market_cap'], cur)}</td>
            </tr>"""
        )
    return f"""<div class="overview-table">
    <table>
      <thead><tr>
        <th>{t("th_symbol")}</th><th>{t("th_price")}</th><th>{t("th_day")}</th><th>{t("th_week")}</th><th>{t("th_month")}</th><th>{t("th_market_cap")}</th>
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
        cur = d.get("currency_symbol", "$")
        dc, dc_cls = fmt_change(d["day_change"])
        wc, wc_cls = fmt_change(d["week_change"])
        mc, mc_cls = fmt_change(d["month_change"])
        vol_str, _vol_cls = volume_badge(d["volume"], d["avg_volume"])

        news_html = ""
        if d["news"]:
            items = []
            for n in d["news"][:3]:
                title = news_translations.get(n["title"], n["title"])
                analysis = news_analyses.get(n["title"], "")
                if analysis:
                    items.append(f"""<div class="sc-news-item">
  <div class="sc-news-title">{title}<span class="sc-news-src">{n["publisher"]}</span></div>
  <div class="sc-analysis">{analysis}</div>
</div>""")
                else:
                    items.append(f'<div class="sc-news-item"><div class="sc-news-title">{title}<span class="sc-news-src">{n["publisher"]}</span></div></div>')
            news_html = '<div class="sc-news">' + "".join(items) + "</div>"

        chart_hint = t("chart_intraday") if d["chart_type"] == "1d" else t("chart_recent")
        is_up = (d.get("month_change") or 0) >= 0
        chart_b64 = render_chart_png(d["chart_dates"], d["chart_closes"], is_up)

        primary, secondary = _primary_secondary(d)
        cards.append(f"""<div class="stock-card">
  <div class="sc-header">
    <div>
      <div class="sc-symbol">{primary}</div>
      <div class="sc-name">{secondary} &middot; {d['market']}</div>
    </div>
    <div class="sc-price">{fmt_price(d['price'], cur)}</div>
  </div>
  <div class="sc-changes">
    <span>{t("label_day")} <b class="{dc_cls}">{dc}</b></span>
    <span>{t("label_week")} <b class="{wc_cls}">{wc}</b></span>
    <span>{t("label_month")} <b class="{mc_cls}">{mc}</b></span>
  </div>
  <div class="sc-info">
    <span>{t("label_market_cap")} {nm(d['market_cap'], cur)}</span>
    {f'<span>{t("label_pe")} {d["pe_ratio"]:.1f}</span>' if d.get("pe_ratio") else ''}
    <span>{t("label_52w_high")} {fmt_price(d['high_52w'], cur)}</span>
    <span>{t("label_52w_low")} {fmt_price(d['low_52w'], cur)}</span>
    <span>{t("label_volume")} {vol_str}</span>
  </div>
  <div class="chart-wrap">
    <img src="data:image/png;base64,{chart_b64}" alt="{d['symbol']}走势图" />
  </div>
  <div class="chart-label">{chart_hint}</div>
  {news_html}
</div>""")
    return "\n".join(cards)
