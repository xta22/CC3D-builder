#!/usr/bin/env python3
"""Plot explicit NPC component cells from RuleParser audit CSV data."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from html import escape
from pathlib import Path


ROLE_COLORS = {
    "inner_membrane": "#d8a65a",
    "outer_membrane": "#c58b37",
    "assembly_site": "#64748b",
    "y_complex": "#0072bc",
    "connecting_complex": "#63a83a",
    "channel_complex": "#b1123b",
    "nup205_inner_ring": "#e6531f",
    "nup188_inner_ring": "#82349a",
    "pore_lumen": "#111827",
}

STAGE_COLORS = {
    "membrane": "#d8a65a",
    "seed": "#64748b",
    "y_complex_scaffold": "#0072bc",
    "connecting_complex": "#63a83a",
    "channel_complex": "#b1123b",
    "inner_ring": "#82349a",
    "mature": "#111827",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot component-as-cell NPC maps from global_simulation_history.csv.")
    parser.add_argument(
        "--input",
        default=None,
        help="Input audit CSV. Defaults to Rules_project/simulation_time_series/global_simulation_history.csv.",
    )
    parser.add_argument("--system", default="npc", help="Subcellular system id.")
    parser.add_argument(
        "--timepoints",
        default="0,250,500,1000,1500,2000",
        help="Comma-separated target MCS values. The nearest audited MCS is used.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output SVG. Defaults to <input csv directory>/plots/<system>_component_cells.svg.",
    )
    return parser.parse_args()


def resolve_input_path(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path).expanduser()
    candidates = [
        Path("Rules_project/simulation_time_series/global_simulation_history.csv"),
        Path("simulation_time_series/global_simulation_history.csv"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_timepoints(raw: str) -> list[float]:
    values = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError as exc:
            raise SystemExit(f"Invalid timepoint {part!r}") from exc
    if not values:
        raise SystemExit("At least one timepoint is required.")
    return values


def to_float(value: object, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def clean_label(value: object) -> str:
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def required_columns(system: str) -> list[str]:
    prefix = f"subcellular_{system}_"
    return [
        "MCS",
        "X_COM",
        "Y_COM",
        f"{prefix}role",
        f"{prefix}stage",
        f"{prefix}bound",
        f"{prefix}contact_area",
        f"{prefix}site_distance",
    ]


def load_rows(path: Path, system: str) -> dict[float, list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in required_columns(system) if column not in fieldnames]
        if missing:
            raise SystemExit(
                f"Missing component-as-cell columns in {path}: {', '.join(missing)}. "
                "Rerun the component-as-cell NPC simulation first."
            )
        by_mcs: dict[float, list[dict[str, str]]] = defaultdict(list)
        for row in reader:
            by_mcs[to_float(row.get("MCS"))].append(row)
    if not by_mcs:
        raise SystemExit(f"No rows found in {path}")
    return dict(by_mcs)


def nearest_mcs(available: list[float], targets: list[float]) -> list[float]:
    selected = []
    for target in targets:
        value = min(available, key=lambda item: (abs(item - target), item))
        if value not in selected:
            selected.append(value)
    return selected


def bounds(rows_by_mcs: dict[float, list[dict[str, str]]], mcs_values: list[float]) -> tuple[float, float, float, float]:
    xs = []
    ys = []
    for mcs in mcs_values:
        for row in rows_by_mcs[mcs]:
            xs.append(to_float(row.get("X_COM")))
            ys.append(to_float(row.get("Y_COM")))
    if not xs or not ys:
        return 0.0, 1.0, 0.0, 1.0
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0:
        x1 = x0 + 1.0
    if y1 <= y0:
        y1 = y0 + 1.0
    padx = (x1 - x0) * 0.08
    pady = (y1 - y0) * 0.08
    return x0 - padx, x1 + padx, y0 - pady, y1 + pady


def svg_text(x: float, y: float, text: str, size: int = 12, weight: str = "400", anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Arial" font-size="{size}" font-weight="{weight}">{escape(text)}</text>'
    )


def mapper(area: tuple[float, float, float, float], x: float, y: float, width: float, height: float):
    x0, x1, y0, y1 = area

    def sx(value: float) -> float:
        return x + (value - x0) / (x1 - x0) * width

    def sy(value: float) -> float:
        return y + height - (value - y0) / (y1 - y0) * height

    return sx, sy


def draw_panel(
    rows: list[dict[str, str]],
    system: str,
    mode: str,
    area: tuple[float, float, float, float],
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
) -> list[str]:
    prefix = f"subcellular_{system}_"
    sx, sy = mapper(area, x + 12, y + 12, width - 24, height - 24)
    svg = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="#f8fafc" stroke="#cbd5e1"/>',
        svg_text(x + width / 2, y - 8, title, size=13, weight="700"),
    ]
    for row in rows:
        role = clean_label(row.get(f"{prefix}role"))
        stage = clean_label(row.get(f"{prefix}stage"))
        bound = clean_label(row.get(f"{prefix}bound")).lower() in {"true", "1", "yes"}
        contact_area = to_float(row.get(f"{prefix}contact_area"))
        color = ROLE_COLORS.get(role, "#94a3b8") if mode == "role" else STAGE_COLORS.get(stage, "#94a3b8")
        px = sx(to_float(row.get("X_COM")))
        py = sy(to_float(row.get("Y_COM")))
        radius = max(2.3, min(7.2, 2.4 + math.sqrt(max(contact_area, 0.0)) * 0.18))
        opacity = 0.50 + min(0.42, contact_area * 0.012)
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius:.2f}" fill="{color}" opacity="{opacity:.2f}"/>')
        if bound:
            svg.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius + 1.6:.2f}" fill="none" '
                f'stroke="#111827" stroke-width="0.8" opacity="0.70"/>'
            )
    return svg


def legend(x: float, y: float, title: str, colors: dict[str, str]) -> list[str]:
    svg = [svg_text(x, y, title, size=13, weight="700", anchor="start")]
    for index, (label, color) in enumerate(colors.items()):
        yy = y + 22 + index * 20
        svg.append(f'<rect x="{x:.1f}" y="{yy - 10:.1f}" width="12" height="12" fill="{color}"/>')
        svg.append(svg_text(x + 18, yy, label.replace("_", " "), size=11, anchor="start"))
    return svg


def render_svg(rows_by_mcs: dict[float, list[dict[str, str]]], mcs_values: list[float], system: str, output: Path) -> None:
    area = bounds(rows_by_mcs, mcs_values)
    panel_w = 180
    panel_h = 180
    gap = 28
    left = 56
    top = 82
    legend_w = 310
    width = left * 2 + len(mcs_values) * panel_w + max(0, len(mcs_values) - 1) * gap + legend_w
    height = top + panel_h * 2 + 58 + 78
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(left, 32, f"{system} component-as-cell spatial map", size=20, weight="700", anchor="start"),
        svg_text(left, 53, "Each dot is a CC3D cell representing a membrane patch or NPC subcomplex.", size=12, anchor="start"),
        svg_text(left - 10, top + panel_h / 2, "role", size=12, weight="700", anchor="end"),
        svg_text(left - 10, top + panel_h + 58 + panel_h / 2, "stage", size=12, weight="700", anchor="end"),
    ]
    for index, mcs in enumerate(mcs_values):
        x = left + index * (panel_w + gap)
        svg.extend(draw_panel(rows_by_mcs[mcs], system, "role", area, x, top, panel_w, panel_h, f"MCS {mcs:.0f}"))
        svg.extend(draw_panel(rows_by_mcs[mcs], system, "stage", area, x, top + panel_h + 58, panel_w, panel_h, ""))
    legend_x = left + len(mcs_values) * panel_w + max(0, len(mcs_values) - 1) * gap + 34
    svg.extend(legend(legend_x, top, "Role", ROLE_COLORS))
    svg.extend(legend(legend_x, top + 235, "Stage", STAGE_COLORS))
    svg.append("</svg>")
    output.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")
    rows_by_mcs = load_rows(input_path, args.system)
    mcs_values = nearest_mcs(sorted(rows_by_mcs), parse_timepoints(args.timepoints))
    output = Path(args.output).expanduser() if args.output else input_path.parent / "plots" / f"{args.system}_component_cells.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    render_svg(rows_by_mcs, mcs_values, args.system, output)
    print(f"SVG written to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
