import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def render_chart_png(chart_dates, chart_closes, is_up):
    """用 matplotlib 生成走势图，返回 base64 PNG。

    色彩与 render_html.py 的浅色仪表盘配色保持一致：
    - 卡片底色 #ffffff
    - 涨绿 #0d9550 / 跌红 #dc2c3a
    - 刻度文字 #9298a3 / 网格 #e0e5ec
    """
    color = "#0d9550" if is_up else "#dc2c3a"
    bg = "#ffffff"

    fig, ax = plt.subplots(figsize=(6.6, 2.5), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    xs = list(range(len(chart_closes)))
    ax.plot(xs, chart_closes, color=color, linewidth=1.5, clip_on=False)
    ax.fill_between(xs, chart_closes, min(chart_closes), color=color, alpha=0.06, linewidth=0)

    n = len(chart_dates)
    step = max(1, n // 5)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([chart_dates[i] for i in range(0, n, step)], fontsize=9, color="#9298a3")
    ax.tick_params(axis="x", length=0, pad=4)

    ax.yaxis.set_major_locator(ticker.MaxNLocator(4))
    ax.tick_params(axis="y", labelsize=9, colors="#9298a3", length=0, pad=4)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"${v:.1f}"))

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#e0e5ec", linewidth=0.5)

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=bg, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
