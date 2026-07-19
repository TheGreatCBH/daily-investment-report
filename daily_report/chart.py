import base64
import io
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

from .i18n import t

logger = logging.getLogger(__name__)

# 走势图刻度含中文（如「前收」），matplotlib 默认 DejaVu Sans 无中文字形会渲成方框；
# 优先用 macOS 自带中文字体，DejaVu Sans 兜底（不存在的候选 matplotlib 自动跳过）。
plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS", "PingFang HK", "Heiti TC", "STHeiti", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

# 浅色仪表盘配色（与 render_html.py 一致）
UP = "#0d9550"
DOWN = "#dc2c3a"
TICK = "#9298a3"
GRID = "#e0e5ec"
BG = "#ffffff"
BASE = "#b0b6c0"           # 前收基准线
SHADE = "#f3f5f8"          # 盘前/盘后（浅）
SHADE_CLOSED = "#ebeef2"   # 无数据/闭市（更深）

# 美股延长时段（us_extended）压缩参数
GAP_TH = 1.5    # 小时：相邻间隔大于此视为「无数据缺口」
GAP_CAP = 1.0   # 小时：缺口压缩后的等效宽度
PP_SCALE = 0.4  # 盘前/盘后时间压缩系数（放大常规盘占比）

# session 市场（港股/A股）压缩参数
LUNCH_CAP = 0.35       # 午休压缩后的等效宽度
LUNCH_TH = 0.75        # 相邻间隔大于此（且小于隔夜阈值）视为午休缺口
OVERNIGHT_TH = 3.0     # 相邻间隔大于此视为跨日/隔夜（午休最多约 1.5h，远小于隔夜约 17h）
OVERNIGHT_CAP = 1.0    # 隔夜缺口压缩后的等效宽度


def render_chart_png(chart_dates, chart_closes, is_up, currency="$", intraday=None):
    """用 matplotlib 生成走势图，返回 base64 PNG。

    intraday 提供且含时间戳时走新几何渲染（颜色绑当日涨跌、前收基准线、
    时间轴压缩、分段底纹）：
      - market_kind == "us_extended"：美股 2–3 日延长时段（盘前后 + 跨日 jump + 底纹）
      - market_kind == "session"：港股/A 股单交易日（LEAD 盘前压缩段 + 午休压缩，无底纹不拖尾）
    intraday 缺失或渲染异常时回退到 fallback（老逻辑，仅按 is_up 着色）。
    """
    if intraday and intraday.get("timestamps"):
        kind = intraday.get("market_kind")
        try:
            if kind == "us_extended":
                return _render_extended(intraday, currency)
            if kind == "session":
                return _render_session(intraday, currency)
        except Exception as e:  # 几何渲染失败不能拖垮整份报告，退回 fallback
            logger.warning("intraday 图渲染失败 [%s]，回退 fallback: %s", kind, e)

    return _render_fallback(chart_dates, chart_closes, is_up, currency)


def _finish(fig):
    """统一收尾：存 PNG → base64。"""
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=BG, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _style_axes(ax, currency):
    """y 轴刻度 / 网格 / 去 spine 的公共样式。价格标签统一 2 位小数。"""
    ax.yaxis.set_major_locator(ticker.MaxNLocator(4))
    ax.tick_params(axis="y", labelsize=9, colors=TICK, length=0, pad=4)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{currency}{v:.2f}"))
    ax.tick_params(axis="x", length=0, pad=4)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.5)


def _render_fallback(chart_dates, chart_closes, is_up, currency):
    """老逻辑：等距 index 折线 + 简单填充；仅按 is_up 着色。

    chart_closes 为空时（行情数据全部缺失）渲染占位空图，避免 min() 抛 ValueError。
    """
    if not chart_closes:
        chart_dates, chart_closes = ["--"], [0]

    color = UP if is_up else DOWN
    fig, ax = plt.subplots(figsize=(6.6, 2.5), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    xs = list(range(len(chart_closes)))
    ax.plot(xs, chart_closes, color=color, linewidth=1.5, clip_on=False)
    ax.fill_between(xs, chart_closes, min(chart_closes), color=color, alpha=0.06, linewidth=0)

    n = len(chart_dates)
    step = max(1, n // 5)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([chart_dates[i] for i in range(0, n, step)], fontsize=9, color=TICK)
    _style_axes(ax, currency)
    return _finish(fig)


def _dedup_ticks(raw, min_gap):
    """raw = [(x, label), ...]，按 x 排序后去掉挤在一起（间距 <= min_gap）的刻度。"""
    raw = sorted(raw)
    ticks, labels, last_x = [], [], -1e9
    for x, lb in raw:
        if x - last_x > min_gap:
            ticks.append(x)
            labels.append(lb)
            last_x = x
    return ticks, labels


def _render_extended(d, currency):
    """美股延长时段：搬 mockup_chart3.py 的几何逻辑。

    d 需含 timestamps(tz-aware) / closes / sessions(pre|regular|post) / prev_close / now。
    """
    ts = d["timestamps"]
    ys = d["closes"]
    sess = d["sessions"]
    prev_close = d["prev_close"]
    now_dt = d["now"]

    # x 轴：piecewise 线性 time-warp，压缩大缺口与盘前后
    xs = [0.0]
    gaps = []
    for i in range(1, len(ts)):
        dt_h = (ts[i] - ts[i - 1]).total_seconds() / 3600.0
        if dt_h > GAP_TH:
            xs.append(xs[-1] + GAP_CAP)
            gaps.append(i)
        else:
            scale = PP_SCALE if sess[i] in ("pre", "post") else 1.0
            xs.append(xs[-1] + dt_h * scale)

    up = ys[-1] >= prev_close
    color = UP if up else DOWN

    # now 的压缩后 x（末段实时差，不压缩，通常 <2h）
    tail_h = (now_dt - ts[-1]).total_seconds() / 3600.0
    x_now = xs[-1] + min(max(tail_h, 0.0), GAP_CAP)

    fig, ax = plt.subplots(figsize=(6.6, 2.5), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 盘前/盘后底纹（分连续块上色，避免跨缺口连成一片）
    for label in ("pre", "post"):
        idxs = [k for k, s in enumerate(sess) if s == label]
        i = 0
        while i < len(idxs):
            j = i
            while j + 1 < len(idxs) and idxs[j + 1] == idxs[j] + 1:
                j += 1
            ax.axvspan(xs[idxs[i]], xs[idxs[j]], color=SHADE, zorder=0)
            i = j + 1

    # 无数据段：更深底纹（隔夜缺口 + 盘后到 now）
    for g in gaps:
        ax.axvspan(xs[g - 1], xs[g], color=SHADE_CLOSED, zorder=0)
    ax.axvspan(xs[-1], x_now, color=SHADE_CLOSED, zorder=0)

    # 前收基准线
    ax.axhline(prev_close, color=BASE, lw=0.9, ls=(0, (4, 3)), alpha=0.7, zorder=1)

    # 连续填充（贯穿全宽，含虚线段：绿/红面积不断）
    bounds = [0] + gaps + [len(ts)]
    fx, fy = [], []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        fx += xs[a:b]
        fy += ys[a:b]
        if b < len(ts):
            fx += [xs[b]]        # 缺口平段（停在缺口前最后价）
            fy += [ys[b - 1]]
    fx += [x_now]
    fy += [ys[-1]]
    ax.fill_between(fx, fy, prev_close, color=color, alpha=0.07, lw=0, zorder=1)

    # 分段真实曲线；缺口处平虚线 + 实线 jump
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        ax.plot(xs[a:b], ys[a:b], color=color, lw=1.5, zorder=3)
    for g in gaps:
        ax.plot([xs[g - 1], xs[g]], [ys[g - 1], ys[g - 1]], color=color, lw=1.5,
                ls=(0, (3, 3)), zorder=3)
        ax.plot([xs[g], xs[g]], [ys[g - 1], ys[g]], color=color, lw=2.0, zorder=4)
    # 末段盘后收 → now：平虚线
    ax.plot([xs[-1], x_now], [ys[-1], ys[-1]], color=color, lw=1.5, ls=(0, (3, 3)), zorder=3)

    ax.set_xlim(-0.3, x_now + 0.3)

    # 刻度：关键节点（前收 / 前一日盘后 20:00 / 盘前开 04:00 / 开盘 09:30 / 盘中 12:00 / 收盘 16:00 / 盘后 20:00 / now）
    def nearest(target):
        return min(range(len(ts)), key=lambda i: abs((ts[i] - target).total_seconds()))

    prev_ts, today_ts = ts[0], ts[-1]
    raw = [(0.0, prev_ts.strftime("%H:%M"))]
    for base, h, m in [(prev_ts, 20, 0), (today_ts, 4, 0), (today_ts, 9, 30),
                       (today_ts, 12, 0), (today_ts, 16, 0), (today_ts, 20, 0)]:
        i = nearest(base.replace(hour=h, minute=m, second=0, microsecond=0))
        raw.append((xs[i], f"{h:02d}:{m:02d}"))
    raw.append((x_now, "now"))
    ticks, labels = _dedup_ticks(raw, 0.6)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=8, color=TICK)

    _style_axes(ax, currency)
    return _finish(fig)


def _render_session(d, currency):
    """港股/A 股单交易日：搬 hk_mockup.py 的几何逻辑。

    d 需含 timestamps(tz-aware，已裁到最近一交易日) / closes / prev_close /
    lead(盘前压缩段宽度) / tick_hm(日内刻度候选整点列表)。
    """
    ts = d["timestamps"]
    ys = d["closes"]
    prev_close = d["prev_close"]
    lead = d.get("lead", 1.0)
    tick_hm = d.get("tick_hm", [])

    # x 轴：LEAD 压缩盘前 → 开盘 → 日内。两级缺口：
    #   午休（LUNCH_TH < Δ < OVERNIGHT_TH）→ 压 LUNCH_CAP、细连线
    #   跨日/隔夜（Δ >= OVERNIGHT_TH）→ 压 OVERNIGHT_CAP、加粗 jump
    sx = [lead]
    lunch, overnight = [], []
    for i in range(1, len(ts)):
        dt_h = (ts[i] - ts[i - 1]).total_seconds() / 3600.0
        if dt_h >= OVERNIGHT_TH:
            sx.append(sx[-1] + OVERNIGHT_CAP)
            overnight.append(i)
        elif dt_h > LUNCH_TH:
            sx.append(sx[-1] + LUNCH_CAP)
            lunch.append(i)
        else:
            sx.append(sx[-1] + dt_h)
    gaps = sorted(lunch + overnight)

    up = ys[-1] >= prev_close
    color = UP if up else DOWN

    fig, ax = plt.subplots(figsize=(6.6, 2.5), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 无数据段：更深底纹（盘前压缩段 + 午休 + 隔夜）
    ax.axvspan(0, lead, color=SHADE_CLOSED, zorder=0)
    for g in gaps:
        ax.axvspan(sx[g - 1], sx[g], color=SHADE_CLOSED, zorder=0)

    ax.axhline(prev_close, color=BASE, lw=0.9, ls=(0, (4, 3)), alpha=0.7, zorder=1)
    # 盘前压缩段：曲线同色平虚线 + 开盘 jump 实线加粗
    ax.plot([0, lead], [prev_close, prev_close], color=color, lw=1.5, ls=(0, (3, 3)), zorder=3)
    ax.plot([lead, lead], [prev_close, ys[0]], color=color, lw=2.0, zorder=4)

    # 连续填充（含午休/隔夜平段：绿/红面积不断）
    bounds = [0] + gaps + [len(ts)]
    fx, fy = [], []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        fx += sx[a:b]
        fy += ys[a:b]
        if b < len(ts):
            fx += [sx[b]]
            fy += [ys[b - 1]]
    ax.fill_between(fx, fy, prev_close, color=color, alpha=0.07, lw=0, zorder=1)

    # 日内曲线（缺口处断开）
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        ax.plot(sx[a:b], ys[a:b], color=color, lw=1.5, zorder=3)
    # 午休：短平虚线 + 细连线（非加粗，区别于跨日）
    for g in lunch:
        ax.plot([sx[g - 1], sx[g]], [ys[g - 1], ys[g - 1]], color=color, lw=1.5,
                ls=(0, (3, 3)), zorder=3)
        ax.plot([sx[g], sx[g]], [ys[g - 1], ys[g]], color=color, lw=1.0, alpha=0.6, zorder=3)
    # 隔夜/跨日：平虚线 + 加粗实线 jump 进入次日
    for g in overnight:
        ax.plot([sx[g - 1], sx[g]], [ys[g - 1], ys[g - 1]], color=color, lw=1.5,
                ls=(0, (3, 3)), zorder=3)
        ax.plot([sx[g], sx[g]], [ys[g - 1], ys[g]], color=color, lw=2.0, zorder=4)

    ax.set_xlim(-0.2, sx[-1] + 0.2)

    # 刻度：前收(x=0) / 首日开盘 / 跨日后各日开盘 / 最后一日候选整点 / 末 bar
    tz = ts[0].tz
    last_day = ts[-1].date()
    last_day_idxs = [i for i in range(len(ts)) if ts[i].date() == last_day]

    def nearest_to(h, m):
        # 只在最后一日的 bar 里找：跨日残段若只有上午，(14,30) 这类整点在全局最近
        # 会绑到残段末 bar 上、误标成「14:30」。限定当日范围避免错标。
        target = pd.Timestamp(last_day.strftime("%Y-%m-%d") + f" {h:02d}:{m:02d}", tz=tz)
        return min(last_day_idxs, key=lambda i: abs((ts[i] - target).total_seconds()))

    raw = [(0.0, t("chart_prev_close")), (lead, ts[0].strftime("%H:%M"))]
    for g in overnight:  # 跨日后次日开盘
        raw.append((sx[g], ts[g].strftime("%H:%M")))
    for h, m in tick_hm:
        i = nearest_to(h, m)
        raw.append((sx[i], f"{h:02d}:{m:02d}"))
    raw.append((sx[-1], ts[-1].strftime("%H:%M")))
    ticks, labels = _dedup_ticks(raw, 0.5)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=8, color=TICK)

    _style_axes(ax, currency)
    return _finish(fig)
