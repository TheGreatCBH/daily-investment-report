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
        return f"${val / 1e12:.2f}T"
    return f"${val / 1e9:.0f}B"


def volume_badge(vol, avg):
    if not vol or not avg or avg == 0:
        return ("-", "")
    r = vol / avg
    if r >= 1.5:
        return (f"{vol:,.0f} 放量 {r:.1f}x", "hot")
    elif r <= 0.5:
        return (f"{vol:,.0f} 缩量 {r:.1f}x", "cold")
    return (f"{vol:,.0f}", "")
