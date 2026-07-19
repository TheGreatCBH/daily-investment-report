import logging
from datetime import datetime
from datetime import time as dtime

import pandas as pd
import yfinance as yf
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


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
    except Exception as e:
        logger.warning("yfinance Search 失败 [%s]: %s", term, e)
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


def fetch_ticker(symbol, search_terms=None, name=None, description=None):
    """统一入口：按 symbol 后缀分派到 yfinance 或 akshare。

    name: watchlist.json 中用户填写的显示名；用于 A 股（akshare 元数据偶发不可用时的兜底）。
    yfinance 分支会用 ticker info 里的 longName/shortName，name 参数仅当所有自动来源都失败时兜底。
    description: watchlist.json 中标的描述，透传进返回 dict 供 summarize_stock_news 的 LLM 相关性判断使用。
    """
    market = _detect_market(symbol)

    if market in ("SH", "SZ"):
        # A 股：行情 + 新闻全部走 akshare
        from .market_data_cn import fetch_a_share
        return fetch_a_share(symbol, search_terms, name=name, description=description)

    data = _fetch_yf_ticker(symbol, search_terms, market, description)
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


def _fetch_yf_ticker(symbol, search_terms, market, description=None):
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
        month_close = df_1mo.iloc[0]["Close"]
        last_close = df_1mo.iloc[-1]["Close"]
        # 停牌/异常导致基准价为 0 时返回 None，避免 ZeroDivisionError 拖垮整只标的
        week_change = (last_close - week_close) / week_close * 100 if week_close else None
        month_change = (last_close - month_close) / month_close * 100 if month_close else None
    else:
        week_change = month_change = None

    chart_type = "1d" if len(df_1d) > 10 else "fallback"
    chart_dates = [d.strftime("%H:%M") for d in df_1d.index]
    chart_closes = [round(v, 2) for v in df_1d["Close"].tolist()]

    # 新几何走势图数据（前收基准线 + 时段压缩 + 底纹）；helper 返回 None 时 chart 回退 fallback
    if market in ("US", "TO"):
        intraday = _build_us_intraday(t, df_1mo)
    elif market == "HK":
        intraday = _build_session_intraday(
            t, "Asia/Hong_Kong", [(11, 0), (12, 0), (13, 0), (14, 30)], df_daily=df_1mo)
    else:
        intraday = None

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
            dt = date_parser.parse(pub_str)
            if (datetime.now(dt.tzinfo) - dt).days > max_age_days:
                continue
        except Exception as e:
            # 日期无法解析时保留该条（宁可偶发旧闻，也不静默丢掉可能的新闻），但记 debug 便于排查
            logger.debug("新闻日期解析失败，保留该条 [%r]: %s", pub_str, e)
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
        "intraday": intraday,
        # search_terms / description 回灌进 dict，供 summarize_stock_news 的 ETF 关键词兜底
        # 与 LLM 相关性判断使用（否则那段逻辑拿不到值，等同死代码）
        "search_terms": search_terms,
        "description": description or "",
        "news": news_items,
    }


def _classify_us(ts):
    """按 ET 本地时间把一个 bar 归为 pre / regular / post。"""
    tt = ts.time()
    if tt < dtime(9, 30):
        return "pre"
    if tt >= dtime(16, 0):
        return "post"
    return "regular"


def _build_us_intraday(t, df_daily):
    """美股/加股延长时段（含盘前后 + 前一交易日盘后）：组装 chart.py 的 us_extended 契约。

    df_daily：已拉的日线（period="1mo"），取 iloc[-2] 作前收、其日期 16:00 ET 作起点。
    数据不足时返回 None → chart 回退 fallback。
    """
    ET = "America/New_York"
    try:
        intra = t.history(period="3d", interval="5m", prepost=True)
    except Exception as e:
        logger.warning("美股延长时段分钟线拉取失败: %s", e)
        return None
    if intra.empty or len(df_daily) < 2:
        return None

    # 前收基准 = iloc[-2]：yfinance 日线 iloc[-1] 恒为「当前会话」（= info.currentPrice，
    # 盘前/盘中/盘后乃至隔夜都不会提前翻到下一日历日），故 iloc[-2] 恒 = info.previousClose，
    # 与卡片 day_change 的基准一致。不要改用 now.date() 找「早于今日」——那会在隔夜时段
    # 把当前会话误判成「昨日」、基准整体错取一天（实测 03:07 ET 会退化成只画盘后段）。
    prev_close = float(df_daily["Close"].iloc[-2])
    prev_day = df_daily.index[-2]
    start_dt = prev_day.normalize() + pd.Timedelta(hours=16)  # 前一交易日 16:00 ET

    idx = intra.index
    idx = idx.tz_localize(ET) if idx.tz is None else idx.tz_convert(ET)
    start_dt = start_dt.tz_localize(ET) if start_dt.tz is None else start_dt.tz_convert(ET)
    now_dt = pd.Timestamp.now(tz=ET)

    ts, closes, sessions = [], [], []
    for tstamp, c in zip(idx, intra["Close"].tolist()):
        if tstamp >= start_dt and pd.notna(c):
            ts.append(tstamp)
            closes.append(round(float(c), 2))
            sessions.append(_classify_us(tstamp))
    if len(ts) < 2:
        return None
    return {
        "market_kind": "us_extended",
        "timestamps": ts,
        "closes": closes,
        "sessions": sessions,
        "prev_close": prev_close,
        "now": now_dt,
    }


def _build_session_intraday(t, tz, tick_hm, lead=1.0, df_daily=None):
    """港股 / A 股（无盘前后）单交易日走势，组装 chart.py 的 session 契约。

    今日数据完整（收盘后跑）→ 只画今日；今日不完整（盘中 / NaN / 未开盘）→ 画
    「上一完整交易日 + 今日残段」，跨日由 chart 侧的隔夜 jump 连接。
    基准线 = 所画首日之前的日线收盘（即前两个交易日收盘）。NaN 分钟 bar 一律过滤。

    t：yfinance Ticker（港股 .HK / A 股 .SS/.SZ 均可，A 股分钟线走 yfinance 比 akshare
    当日 5m 前复权价更可靠——后者当日实时常返回 NaN）。df_daily 缺省时内部自取。
    数据不足返回 None → chart 回退 fallback。
    """
    try:
        intra = t.history(period="7d", interval="5m")
        if df_daily is None:
            df_daily = t.history(period="1mo")
    except Exception as e:
        logger.warning("session 分钟线拉取失败: %s", e)
        return None
    if intra.empty or df_daily is None or len(df_daily) < 2:
        return None

    idx = intra.index
    idx = idx.tz_localize(tz) if idx.tz is None else idx.tz_convert(tz)

    # 过滤 NaN，按交易日分组（保持时间序）
    day_bars = {}
    for tstamp, c in zip(idx, intra["Close"].tolist()):
        if pd.notna(c):
            day_bars.setdefault(tstamp.date(), []).append((tstamp, round(float(c), 2)))
    days = sorted(day_bars)
    if not days:
        return None

    # 完整性阈值：满日基准只从「今日之前」各日取——若把今日也算进 max，今日 bar 数
    # 恰为最多时阈值恒被满足，盘中残段就永远不会去借上一完整交易日。
    today = days[-1]
    prior = days[:-1]
    full_n = max((len(day_bars[d]) for d in prior), default=len(day_bars[today]))
    today_full = len(day_bars[today]) >= full_n * 0.8

    if today_full or len(days) == 1:
        picked = [today]
    else:
        prev_full = next((d for d in reversed(days[:-1])
                          if len(day_bars[d]) >= full_n * 0.8), None)
        picked = [prev_full, today] if prev_full else [today]

    # 基准线 = 所画首日之前的日线收盘
    first_day = picked[0]
    basis = None
    for dd, cc in zip(reversed(df_daily.index.tolist()), reversed(df_daily["Close"].tolist())):
        if dd.date() < first_day and pd.notna(cc):
            basis = float(cc)
            break
    if basis is None:
        basis = float(df_daily["Close"].iloc[-2])

    ts, closes = [], []
    for d in picked:
        for tstamp, c in day_bars[d]:
            ts.append(tstamp)
            closes.append(c)
    if len(ts) < 2:
        return None
    return {
        "market_kind": "session",
        "timestamps": ts,
        "closes": closes,
        "prev_close": basis,
        "lead": lead,
        "tick_hm": tick_hm,
    }


def fetch_macro_news():
    # 不在此吞异常：让失败抛给 pipeline 的 retry + except（那里有 WARNING 日志和空列表兜底），
    # 否则网络故障会被静默成「OK (0 条)」且不触发重试。
    sp = yf.Ticker("^GSPC")
    raw = sp.news[:8] if sp.news else []
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
