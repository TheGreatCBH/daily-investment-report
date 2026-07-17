"""最小化单元测试，覆盖核心纯函数，无网络/LLM 依赖。"""
import pytest

from daily_report.market_data import _detect_market
from daily_report.formatting import fmt_change, nm, volume_badge
from daily_report.render_html import _primary_secondary


class TestDetectMarket:
    def test_us_no_suffix(self):
        assert _detect_market("NVDA") == "US"

    def test_us_aapl(self):
        assert _detect_market("AAPL") == "US"

    def test_sh(self):
        assert _detect_market("600519.SS") == "SH"

    def test_sz(self):
        assert _detect_market("000001.SZ") == "SZ"

    def test_hk(self):
        assert _detect_market("0700.HK") == "HK"

    def test_toronto(self):
        assert _detect_market("ZEB.TO") == "TO"


class TestFmtChange:
    def test_positive(self):
        text, cls = fmt_change(1.5)
        assert text == "+1.50%"
        assert cls == "up"

    def test_negative(self):
        text, cls = fmt_change(-2.3)
        assert text == "-2.30%"
        assert cls == "down"

    def test_zero(self):
        text, cls = fmt_change(0.0)
        assert text == "+0.00%"
        assert cls == "up"

    def test_none(self):
        text, cls = fmt_change(None)
        assert text == "-"
        assert cls == ""


class TestNm:
    def test_trillions(self):
        assert nm(1.5e12) == "$1.50T"

    def test_billions(self):
        assert nm(500e9) == "$500B"

    def test_none(self):
        assert nm(None) == "-"

    def test_custom_currency(self):
        assert nm(2e12, "¥") == "¥2.00T"
        assert nm(300e9, "HK$") == "HK$300B"


class TestPrimarySecondary:
    def test_a_share_sh(self):
        primary, secondary = _primary_secondary({"symbol": "600519.SS", "name": "贵州茅台"})
        assert primary == "贵州茅台"
        assert secondary == "600519.SS"

    def test_a_share_sz(self):
        primary, secondary = _primary_secondary({"symbol": "000001.SZ", "name": "平安银行"})
        assert primary == "平安银行"
        assert secondary == "000001.SZ"

    def test_hk(self):
        primary, secondary = _primary_secondary({"symbol": "0700.HK", "name": "腾讯控股"})
        assert primary == "腾讯控股"
        assert secondary == "0700.HK"

    def test_us(self):
        primary, secondary = _primary_secondary({"symbol": "NVDA", "name": "NVIDIA"})
        assert primary == "NVDA"
        assert secondary == "NVIDIA"


class TestWatchlistPathOverride:
    """WATCHLIST_PATH 环境变量覆盖：用于 demo/测试指向备用 watchlist。"""

    def test_env_override(self, monkeypatch):
        import importlib

        from daily_report import config

        monkeypatch.setenv("WATCHLIST_PATH", "/tmp/custom_watchlist.json")
        try:
            importlib.reload(config)
            assert str(config.WATCHLIST_PATH) == "/tmp/custom_watchlist.json"
        finally:
            monkeypatch.delenv("WATCHLIST_PATH", raising=False)
            importlib.reload(config)

    def test_default_falls_back_to_repo_root(self, monkeypatch):
        import importlib

        from daily_report import config

        monkeypatch.delenv("WATCHLIST_PATH", raising=False)
        importlib.reload(config)
        assert config.WATCHLIST_PATH.name == "watchlist.json"
        assert config.WATCHLIST_PATH.parent == config.ROOT


class TestNmTiers:
    """市值缩写新增 M 档，A 股小盘 <1e9 不再显示 ¥0B。"""

    def test_sub_billion_uses_m(self):
        assert nm(5e8) == "$500M"
        assert nm(8e8, "¥") == "¥800M"

    def test_billion_boundary(self):
        assert nm(1e9) == "$1B"


class TestVolumeBadge:
    def test_high(self):
        text, cls = volume_badge(1500, 1000)
        assert cls == "hot"
        assert "1.5x" in text

    def test_low(self):
        _text, cls = volume_badge(400, 1000)
        assert cls == "cold"

    def test_normal(self):
        _text, cls = volume_badge(1000, 1000)
        assert cls == ""

    def test_missing(self):
        assert volume_badge(0, 1000) == ("-", "")
        assert volume_badge(1000, 0) == ("-", "")


class TestEscPs:
    """PowerShell 转义需中和 双引号 / backtick / $(...)。"""

    def test_escapes_injection_chars(self):
        from daily_report.notify import _esc_ps

        out = _esc_ps('a"$(x)`b')
        assert '""' in out   # 双引号翻倍
        assert "`$" in out   # $ 被 backtick 转义
        assert "``" in out   # backtick 翻倍


class TestExtractJson:
    def test_plain(self):
        from daily_report.news_llm import _extract_json

        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_json_fence(self):
        from daily_report.news_llm import _extract_json

        assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self):
        from daily_report.news_llm import _extract_json

        assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}


class TestTranslateNewsTitles:
    """标题翻译分批：去重、分批调用、单批失败不拖垮其余批次。"""

    def _data(self, titles):
        return [{"symbol": "X", "news": [{"title": t} for t in titles]}]

    def test_empty_returns_empty(self):
        from daily_report import news_llm

        assert news_llm.translate_news_titles([]) == {}

    def test_batches_by_size(self, monkeypatch):
        from daily_report import news_llm

        calls = []
        monkeypatch.setattr(news_llm, "_TRANSLATE_BATCH_SIZE", 2)
        monkeypatch.setattr(news_llm, "_client", lambda: None)
        monkeypatch.setattr(news_llm, "_load_prompt", lambda name: "")

        def fake_batch(client, template, titles):
            calls.append(list(titles))
            return {t: f"译:{t}" for t in titles}

        monkeypatch.setattr(news_llm, "_translate_titles_batch", fake_batch)
        out = news_llm.translate_news_titles(self._data(["a", "b", "c"]))
        # 3 条、批大小 2 → 2 批（[a,b] / [c]）
        assert calls == [["a", "b"], ["c"]]
        assert out == {"a": "译:a", "b": "译:b", "c": "译:c"}

    def test_dedups_by_full_title(self, monkeypatch):
        from daily_report import news_llm

        seen_batches = []
        monkeypatch.setattr(news_llm, "_client", lambda: None)
        monkeypatch.setattr(news_llm, "_load_prompt", lambda name: "")

        def fake_batch(client, template, titles):
            seen_batches.append(list(titles))
            return {t: t for t in titles}

        monkeypatch.setattr(news_llm, "_translate_titles_batch", fake_batch)
        news_llm.translate_news_titles(self._data(["dup", "dup", "other"]))
        assert seen_batches == [["dup", "other"]]

    def test_one_failed_batch_keeps_others(self, monkeypatch):
        from daily_report import news_llm

        monkeypatch.setattr(news_llm, "_TRANSLATE_BATCH_SIZE", 1)
        monkeypatch.setattr(news_llm, "_client", lambda: None)
        monkeypatch.setattr(news_llm, "_load_prompt", lambda name: "")

        def fake_batch(client, template, titles):
            if titles == ["boom"]:
                raise ValueError("simulated truncation")
            return {t: f"译:{t}" for t in titles}

        monkeypatch.setattr(news_llm, "_translate_titles_batch", fake_batch)
        out = news_llm.translate_news_titles(self._data(["ok1", "boom", "ok2"]))
        assert out == {"ok1": "译:ok1", "ok2": "译:ok2"}


class TestRenderChartEmpty:
    """行情数据全空时 render_chart_png 必须返回占位图而非抛 ValueError。"""

    def test_empty_does_not_crash(self):
        from daily_report.chart import render_chart_png

        out = render_chart_png([], [], True)
        assert isinstance(out, str) and len(out) > 0

    def test_empty_with_currency(self):
        from daily_report.chart import render_chart_png

        out = render_chart_png([], [], False, "¥")
        assert isinstance(out, str) and len(out) > 0
