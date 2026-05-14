import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def render_chart_png(chart_dates, chart_closes, is_up):
    """用 matplotlib 生成走势图，返回 base64 PNG"""
    color = "#00c853" if is_up else "#ff3d4f"
    bg = "#161c26"

    fig, ax = plt.subplots(figsize=(6.6, 1.9), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    xs = list(range(len(chart_closes)))
    ax.plot(xs, chart_closes, color=color, linewidth=1.5, clip_on=False)
    ax.fill_between(xs, chart_closes, min(chart_closes), color=color, alpha=0.08, linewidth=0)

    n = len(chart_dates)
    step = max(1, n // 5)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([chart_dates[i] for i in range(0, n, step)], fontsize=7, color="#565c67")
    ax.tick_params(axis="x", length=0, pad=4)

    ax.yaxis.set_major_locator(ticker.MaxNLocator(4))
    ax.tick_params(axis="y", labelsize=7, colors="#565c67", length=0, pad=4)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"${v:.1f}"))

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#1e2733", linewidth=0.5)

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=bg, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
