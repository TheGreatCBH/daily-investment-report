"""最小化单元测试，覆盖核心纯函数，无网络/LLM 依赖。"""
import pytest

from daily_report.market_data import _detect_market
from daily_report.formatting import fmt_change, nm
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
