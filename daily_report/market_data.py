from datetime import datetime

import yfinance as yf


def _detect_market(symbol):
    """根据 yfinance 风格 symbol 推断市场，用于路由数据源 + 决定货币符号。"""
    if symbol.endswith(".SS"):
        return "SH"
    if symbol.endswith(".SZ"):
        return "SZ"
    if symbol.endswith(".HK"):
        return "HK"
    if symbol.endswith(".TO") or symbol.endswith(".V"):
        return "TO"
    return "US"


_CURRENCY = {
    "US": "$",
    "HK": "HK$",
    "TO": "C$",
    "SH": "¥",
    "SZ": "¥",
}


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


def fetch_ticker(symbol, search_terms=None, name=None):
    """统一入口：按 symbol 后缀分派到 yfinance 或 akshare。

    name: watchlist.json 中用户填写的显示名；用于 A 股（akshare 元数据偶发不可用时的兜底）。
    yfinance 分支会用 ticker info 里的 longName/shortName，name 参数仅当所有自动来源都失败时兜底。
    """
    market = _detect_market(symbol)

    if market in ("SH", "SZ"):
        # A 股：行情 + 新闻全部走 akshare
        from .market_data_cn import fetch_a_share
        return fetch_a_share(symbol, search_terms, name=name)

    data = _fetch_yf_ticker(symbol, search_terms, market)
    # watchlist 用户写的 name 永远优先，覆盖 yfinance 的 longName
    # （这样用户在 watchlist.json 里写"诺和诺德"/"腾讯控股"等中文别名能生效）
    if name:
        data["name"] = name

    if market == "HK":
        # 港股新闻补强：akshare 中文新闻覆盖比 yfinance 英文新闻好
        from .market_data_cn import fetch_hk_news_via_ak
        ak_news = fetch_hk_news_via_ak(symbol)
        if ak_news:
            data["news"] = ak_news

    return data


def _fetch_yf_ticker(symbol, search_terms, market):
    t = yf.Ticker(symbol)
    info = t.info

    # df_1mo: ~22 行交易日数据（用于月/周变化；5 交易日 ≈ 1 自然周，22 交易日 ≈ 1 自然月）
    df_1mo = t.history(period="1mo")
    df_1d = t.history(period="1d", interval="5m")
    if df_1d.empty:
        df_1d = t.history(period="5d", interval="30m")
        if df_1d.empty:
            df_1d = df_1mo

    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    current = info.get("currentPrice") or info.get("regularMarketPrice")
    day_change = ((current - prev_close) / prev_close * 100) if current and prev_close else None

    if len(df_1mo) >= 2:
        # 5 交易日前 ≈ 1 周前；iloc[-6] 多取 1 行作为缓冲
        week_close = df_1mo.iloc[-6]["Close"] if len(df_1mo) >= 6 else df_1mo.iloc[0]["Close"]
        week_change = (df_1mo.iloc[-1]["Close"] - week_close) / week_close * 100
        month_change = (df_1mo.iloc[-1]["Close"] - df_1mo.iloc[0]["Close"]) / df_1mo.iloc[0]["Close"] * 100
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
        "currency_symbol": _CURRENCY.get(market, "$"),
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
