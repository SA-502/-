"""رسوم SVG بسيطة للتقرير (بدون مكتبات رسم) — تُضمَّن مباشرة في قالب HTML."""

import math
import re
from html import escape as _escape

import arabic_reshaper
from bidi.algorithm import get_display

_ARABIC = re.compile(r"[\u0600-\u06FF]")

INK = "#1f2937"
MUTED = "#6b7280"
GRID = "#e5e7eb"
SUN = "#f59e0b"
LOAD = "#2563eb"
GOOD = "#059669"
BAD = "#dc2626"


def escape(text: str) -> str:
    """نص SVG: WeasyPrint لا يشكّل الحروف العربية داخل SVG، فنمرر الحروف مشكّلة وبالترتيب المرئي."""
    if _ARABIC.search(text):
        text = get_display(arabic_reshaper.reshape(text))
    return _escape(text)


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * exp:
            return step * exp
    return 10 * exp


def _fmt(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.3g}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.3g}k"
    return f"{value:.0f}"


def monthly_chart(production: list[float], consumption: list[float] | None, labels: list[str], legend: tuple[str, str]) -> str:
    """أعمدة الإنتاج الشهري وخط الاستهلاك. الأشهر من اليمين لليسار لتناسب القراءة العربية."""
    width, height, left, right, top, bottom = 680, 250, 20, 50, 30, 36
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = _nice_max(max(production + (consumption or [0])))
    slot = plot_w / 12
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-size="11" font-family="inherit">']
    for i in range(5):
        value = peak * i / 4
        y = top + plot_h - plot_h * i / 4
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{left + plot_w + 6}" y="{y + 4:.1f}" fill="{MUTED}">{_fmt(value)}</text>')
    xs = []
    for m in range(12):
        x_center = left + plot_w - slot * (m + 0.5)
        xs.append(x_center)
        bar_h = plot_h * production[m] / peak
        parts.append(
            f'<rect x="{x_center - slot * 0.32:.1f}" y="{top + plot_h - bar_h:.1f}" width="{slot * 0.64:.1f}" height="{bar_h:.1f}" fill="{SUN}" rx="2"/>'
        )
        parts.append(f'<text x="{x_center:.1f}" y="{height - bottom + 16}" text-anchor="middle" fill="{INK}">{escape(labels[m])}</text>')
    if consumption:
        points = " ".join(f"{xs[m]:.1f},{top + plot_h - plot_h * consumption[m] / peak:.1f}" for m in range(12))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{LOAD}" stroke-width="2.5"/>')
        for m in range(12):
            parts.append(f'<circle cx="{xs[m]:.1f}" cy="{top + plot_h - plot_h * consumption[m] / peak:.1f}" r="3" fill="{LOAD}"/>')
    lx = left + plot_w
    parts.append(f'<rect x="{lx - 12}" y="6" width="12" height="12" fill="{SUN}" rx="2"/>')
    parts.append(f'<text x="{lx - 18}" y="16" text-anchor="end" fill="{INK}">{escape(legend[0])}</text>')
    if consumption:
        parts.append(f'<line x1="{lx - 160}" x2="{lx - 146}" y1="12" y2="12" stroke="{LOAD}" stroke-width="2.5"/>')
        parts.append(f'<text x="{lx - 166}" y="16" text-anchor="end" fill="{INK}">{escape(legend[1])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _ticks(low: float, high: float, count: int = 4) -> list[float]:
    raw = (high - low) / count or 1.0
    step = _nice_max(raw)
    first = math.floor(low / step) * step
    ticks = [first]
    while ticks[-1] < high - 1e-9:
        ticks.append(ticks[-1] + step)
    return ticks


def cashflow_chart(cumulative: list[float], capex: float) -> str:
    """التدفق النقدي التراكمي من السنة 0 (−التكلفة) حتى نهاية العمر؛ السنة 0 يمينًا."""
    width, height, left, right, top, bottom = 680, 220, 20, 60, 16, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [-capex] + cumulative
    ticks = _ticks(min(min(values), 0), max(max(values), 0))
    low, high = ticks[0], ticks[-1]
    span = high - low or 1
    n = len(values) - 1
    to_x = lambda i: left + plot_w - plot_w * (i + 0.5) / (n + 1)
    to_y = lambda v: top + plot_h * (high - v) / span
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-size="11" font-family="inherit">']
    for v in ticks:
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{to_y(v):.1f}" y2="{to_y(v):.1f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{left + plot_w + 6}" y="{to_y(v) + 4:.1f}" fill="{MUTED}">{_fmt(v)}</text>')
    parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{to_y(0):.1f}" y2="{to_y(0):.1f}" stroke="{INK}"/>')
    bar_w = plot_w / (n + 1) * 0.7
    for i, v in enumerate(values):
        y0, y1 = sorted((to_y(0), to_y(v)))
        color = GOOD if v >= 0 else BAD
        parts.append(f'<rect x="{to_x(i) - bar_w / 2:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{max(y1 - y0, 0.5):.1f}" fill="{color}" opacity="0.85"/>')
        if i % 5 == 0:
            parts.append(f'<text x="{to_x(i):.1f}" y="{height - 10}" text-anchor="middle" fill="{INK}">{i}</text>')
    parts.append("</svg>")
    return "".join(parts)


def plan_svg(areas: list[dict], obstructions: list[list[tuple[float, float]]], modules: list[dict], north_label: str) -> str:
    """مخطط علوي بالمتر. areas: [{"ring": [(x, y)...]}]، modules: [{"x","y","w","d","rot"}] (rot = اتجاه الوجه بالدرجات من الشمال)."""
    points = [p for a in areas for p in a["ring"]]
    if not points:
        return ""
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    pad = max(max_x - min_x, max_y - min_y) * 0.06 + 1
    min_x, max_x, min_y, max_y = min_x - pad, max_x + pad, min_y - pad, max_y + pad
    width = 680
    scale = width / (max_x - min_x)
    height = min((max_y - min_y) * scale, 300)
    scale = min(scale, height / (max_y - min_y))
    tx = lambda x: (x - min_x) * scale
    ty = lambda y: (max_y - y) * scale
    ring = lambda pts: " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)

    parts = [f'<svg viewBox="0 0 {width} {height:.0f}" xmlns="http://www.w3.org/2000/svg" font-size="11" font-family="inherit">']
    for area in areas:
        parts.append(f'<polygon points="{ring(area["ring"])}" fill="#f3f4f6" stroke="{INK}" stroke-width="1.5"/>')
    for obs in obstructions:
        parts.append(f'<polygon points="{ring(obs)}" fill="#fee2e2" stroke="{BAD}" stroke-dasharray="4 3"/>')
    for m in modules:
        # المستطيل: العرض على امتداد الصف، العمق باتجاه الوجه
        angle = math.radians(m["rot"])
        fx, fy = math.sin(angle), math.cos(angle)  # اتجاه الوجه (شرق، شمال)
        rx, ry = fy, -fx  # امتداد الصف
        hw, hd = m["w"] / 2, m["d"] / 2
        corners = [
            (m["x"] + sx * hw * rx + sy * hd * fx, m["y"] + sx * hw * ry + sy * hd * fy)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        parts.append(f'<polygon points="{ring(corners)}" fill="#1e3a8a" stroke="#93c5fd" stroke-width="0.4"/>')
    # سهم الشمال ومقياس
    nx, ny = width - 24, 16
    parts.append(f'<path d="M{nx} {ny} l-6 16 l6 -4 l6 4 z" fill="{INK}"/>')
    parts.append(f'<text x="{nx}" y="{ny + 30}" text-anchor="middle" fill="{INK}">{escape(north_label)}</text>')
    bar_m = _nice_max((max_x - min_x) / 6)
    parts.append(f'<line x1="12" x2="{12 + bar_m * scale:.1f}" y1="{height - 12:.0f}" y2="{height - 12:.0f}" stroke="{INK}" stroke-width="3"/>')
    parts.append(f'<text x="12" y="{height - 18:.0f}" fill="{INK}">{bar_m:g} m</text>')
    parts.append("</svg>")
    return "".join(parts)
