"""A 股 / 港股数据接入（走 akshare）。

A 股（`.SS` / `.SZ`）：
  - 日线和分钟线 走 Sina（akshare 的东方财富 quote 接口偶发被限流，Sina 更稳定）
  - 新闻 走 东方财富（不同 endpoint，不受 quote 限流影响）
  - 名称 best-effort 试 东方财富 individual_info_em，失败回退到代码

港股（`.HK`）：行情仍在 yfinance（见 market_data._fetch_yf_ticker），
本模块只补充提供 akshare 中文新闻替换 yfinance 的英文稀疏新闻。
"""
import akshare as ak

from .i18n import t


def _code(symbol):
    """600519.SS -> 600519；0700.HK -> 0700"""
    return symbol.split(".")[0]


def _sina_symbol(symbol):
    """Sina 风格：sh600519 / sz000001"""
    code = _code(symbol)
    if symbol.endswith(".SS"):
        return f"sh{code}"
    return f"sz{code}"


def fetch_a_share(symbol, search_terms=None, name=None):
    """A 股完整 fetch：返回与 yfinance fetch_ticker 同形状的字典。

    name 来自 watchlist.json 用户填写值，作为名称的主源。
    若 name 为空，再 best-effort 试 akshare 个股信息接口，最后回退到代码。
    """
    code = _code(symbol)
    sina_sym = _sina_symbol(symbol)

    # 日线（Sina 全历史，截最近一年用于 52w + 月/周变化）
    df_daily = ak.stock_zh_a_daily(symbol=sina_sym, adjust="qfq")
    if df_daily.empty:
        raise ValueError(f"akshare Sina returned no daily data for {sina_sym}")
    df_year = df_daily.tail(252).reset_index(drop=True)  # 252 交易日 ≈ 1 年

    # 名称：watchlist 用户填写 > akshare 个股信息（best-effort）> 代码
    resolved_name = name
    if not resolved_name:
        try:
            info_df = ak.stock_individual_info_em(symbol=code)
            info = dict(zip(info_df["item"], info_df["value"]))
            resolved_name = str(info.get("股票简称") or code)
        except Exception:
            resolved_name = code

    # 盘中 5 分钟线（最近一天）
    chart_dates, chart_closes, chart_type = [], [], "fallback"
    try:
        df_min = ak.stock_zh_a_minute(symbol=sina_sym, period="5", adjust="qfq")
        if not df_min.empty:
            df_min["day"] = df_min["day"].astype(str)
            last_date = df_min["day"].iloc[-1][:10]
            df_today = df_min[df_min["day"].str.startswith(last_date)]
            if len(df_today) > 5:
                # "2026-05-14 14:55:00" -> "14:55"
                chart_dates = [t[11:16] for t in df_today["day"]]
                chart_closes = [round(float(v), 2) for v in df_today["close"]]
                chart_type = "1d"
    except Exception:
        pass

    if not chart_dates:
        df_m = df_year.tail(30)
        chart_dates = [str(d)[-5:] for d in df_m["date"]]
        chart_closes = [round(float(v), 2) for v in df_m["close"]]

    closes = df_year["close"].astype(float)
    current = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else None
    day_change = (current - prev_close) / prev_close * 100 if prev_close else None

    # 5 交易日 ≈ 1 自然周（iloc[-6] 多取 1 行作缓冲），22 交易日 ≈ 1 自然月
    week_close = float(closes.iloc[-6] if len(closes) >= 6 else closes.iloc[0])
    week_change = (current - week_close) / week_close * 100

    month_close = float(closes.iloc[-22] if len(closes) >= 22 else closes.iloc[0])
    month_change = (current - month_close) / month_close * 100

    high_52w = float(df_year["high"].astype(float).max())
    low_52w = float(df_year["low"].astype(float).min())

    volume_today = float(df_year["volume"].iloc[-1])
    avg_volume = float(df_year["volume"].astype(float).tail(20).mean())

    # 市值 = 流通股 × 现价（Sina 提供的 outstanding_share 字段）
    market_cap = None
    try:
        outstanding = float(df_year["outstanding_share"].iloc[-1])
        market_cap = outstanding * current
    except (KeyError, ValueError, TypeError):
        pass

    return {
        "symbol": symbol,
        "name": resolved_name,
        "market": t("market_sh") if symbol.endswith(".SS") else t("market_sz"),
        "currency_symbol": "¥",
        "price": current,
        "prev_close": prev_close,
        "day_change": day_change,
        "week_change": week_change,
        "month_change": month_change,
        "market_cap": market_cap,
        # Sina 不直接提供 PE；接 stock_a_indicator_lg 是另一次外网调用，性价比低，先留空
        "pe_ratio": None,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "volume": volume_today,
        "avg_volume": avg_volume,
        "chart_dates": chart_dates,
        "chart_closes": chart_closes,
        "chart_type": chart_type,
        "news": _fetch_news_ak(code),
    }


def _fetch_news_ak(code, max_results=5):
    """从东方财富新闻接口拉某代码相关新闻；A 股传 6 位代码，港股传 5 位代码。"""
    try:
        df = ak.stock_news_em(symbol=code)
    except Exception:
        return []
    if df.empty:
        return []
    items = []
    for _, row in df.head(max_results).iterrows():
        items.append({
            "title": str(row.get("新闻标题", "-")),
            "summary": str(row.get("新闻内容", ""))[:200],
            "publisher": str(row.get("文章来源", "-")),
            "published": str(row.get("发布时间", "")),
        })
    return items


def fetch_hk_news_via_ak(symbol):
    """港股 0700.HK -> 00700（5 位代码）从东方财富拉中文新闻。"""
    code = _code(symbol).zfill(5)
    return _fetch_news_ak(code)
