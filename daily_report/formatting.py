from .i18n import t


def fmt_change(val):
    if val is None:
        return ("-", "")
    sign = "+" if val >= 0 else ""
    cls = "up" if val >= 0 else "down"
    return (f"{sign}{val:.2f}%", cls)


def fmt_price(val, currency="$"):
    if val is None:
        return "-"
    return f"{currency}{val:.2f}"


def nm(val, currency="$"):
    """市值缩写：≥1e12 用 T、≥1e9 用 B、否则用 M（避免 A 股小盘 <1e9 显示成 ¥0B）。"""
    if val is None:
        return "-"
    if val >= 1e12:
        return f"{currency}{val / 1e12:.2f}T"
    if val >= 1e9:
        return f"{currency}{val / 1e9:.0f}B"
    return f"{currency}{val / 1e6:.0f}M"


def volume_badge(vol, avg):
    if not vol or not avg:
        return ("-", "")
    r = vol / avg
    if r >= 1.5:
        return (f"{vol:,.0f} {t('high_volume')} {r:.1f}x", "hot")
    elif r <= 0.5:
        return (f"{vol:,.0f} {t('low_volume')} {r:.1f}x", "cold")
    return (f"{vol:,.0f}", "")
