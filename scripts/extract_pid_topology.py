#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract first-pass topology evidence from vector PDF PFD/P&ID drawings."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


TAG_RE = re.compile(
    r"\b(?:"
    r"TK|T|V|P|K|C|E|F|R|H|"
    r"PSV|PRV|TSV|PCV|LCV|FCV|TCV|MOV|XV|SDV|ESDV|BDV|RO|"
    r"PT|PI|PIC|PIT|TT|TI|TIC|TIT|LT|LI|LIC|LIT|FT|FI|FIC|FIT|"
    r"LAH|LAHH|LAL|LALL|PAH|PAHH|PAL|PALL|TAH|TAHH|TAL|TALL|FAL|FAH|"
    r"GD|FD|FG"
    r")[\-_ ]?\d{2,6}[A-Z]?\b",
    re.IGNORECASE,
)

LINE_ID_RE = re.compile(
    r"\b[A-Z]{2,5}-[A-Z0-9]{2,6}-\d{4,8}(?:-[0-9.]+\"?)?(?:-[A-Z0-9]{2,8}){0,3}\b",
    re.IGNORECASE,
)

CONFIDENCE_LABEL = {"high": "高", "medium": "中", "low": "低"}


@dataclasses.dataclass
class TextCandidate:
    text: str
    kind: str
    page: int
    bbox: tuple[float, float, float, float]


@dataclasses.dataclass
class Segment:
    segment_id: str
    page: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    orientation: str


@dataclasses.dataclass
class Component:
    component_id: str
    page: int
    segment_ids: list[str]
    bbox: tuple[float, float, float, float]
    orientation: str
    associated_text: list[dict[str, Any]]
    connections: list[dict[str, Any]]


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract vector-PDF P&ID topology evidence.")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Folder containing PDF drawings.")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output folder.")
    parser.add_argument("--pdf-page-limit", type=int, default=2, help="Maximum pages per PDF to inspect.")
    parser.add_argument("--min-line-length", type=float, default=18.0, help="Ignore shorter vector line segments.")
    parser.add_argument("--join-tolerance", type=float, default=6.0, help="Endpoint tolerance for line components, in PDF points.")
    parser.add_argument("--snap-distance", type=float, default=22.0, help="Max text-to-line distance for associating tags.")
    parser.add_argument("--max-connections-per-component", type=int, default=12)
    parser.add_argument("--include-all-pdfs", action="store_true", help="Inspect every PDF, including tables and non-drawing documents.")
    parser.add_argument("--include-pfd-context", action="store_true", help="Also inspect PFD drawings. Default treats PFD as project context only.")
    parser.add_argument("--include-existing", action="store_true", help="Also inspect drawings whose path contains 已建.")
    parser.add_argument("--include-standard-drawings", action="store_true", help="Include general notes, legends, details, and abbreviation sheets.")
    args = parser.parse_args()

    input_dir = args.input.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    docs: list[dict[str, Any]] = []
    all_connections: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for pdf in sorted(input_dir.rglob("*.pdf")):
        if output_dir in pdf.resolve().parents:
            continue
        if not args.include_existing and is_existing_drawing(pdf):
            skipped.append({"rel_path": str(pdf.relative_to(input_dir)), "reason": "已建图纸默认作为既有装置接口背景，不进入本轮拓扑抽取"})
            continue
        if not args.include_pfd_context and is_pfd_context_drawing(pdf):
            skipped.append({"rel_path": str(pdf.relative_to(input_dir)), "reason": "PFD仅作为项目整体理解基础，不参与逐张P&ID拓扑抽取"})
            continue
        if not args.include_all_pdfs and not is_probable_flow_drawing(pdf):
            skipped.append({"rel_path": str(pdf.relative_to(input_dir)), "reason": "非P&ID流程图，默认不抽取拓扑"})
            continue
        if not args.include_standard_drawings and is_standard_reference_drawing(pdf):
            skipped.append({"rel_path": str(pdf.relative_to(input_dir)), "reason": "通用注释、图例或详图默认不参与逐张P&ID拓扑抽取"})
            continue
        doc_result = analyze_pdf(
            pdf,
            input_dir,
            page_limit=args.pdf_page_limit,
            min_line_length=args.min_line_length,
            join_tolerance=args.join_tolerance,
            snap_distance=args.snap_distance,
            max_connections_per_component=args.max_connections_per_component,
        )
        docs.append(doc_result)
        for page in doc_result["pages"]:
            for component in page["components"]:
                for connection in component["connections"]:
                    row = {
                        "rel_path": doc_result["rel_path"],
                        "page": page["page"],
                        "component_id": component["component_id"],
                        **connection,
                    }
                    all_connections.append(row)

    package = {
        "metadata": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "method": "试验性矢量PDF拓扑证据抽取：文本坐标 + 矢量线段组件 + 位号近邻关联。",
            "limitations": [
                "当前尚不能语义识别P&ID符号。",
                "除非另行确认箭头或管线标注，否则候选连接不能证明工艺流向。",
                "连接关系只是供专家看图复核的拓扑候选证据，不是最终HAZOP结论。",
                "扫描PDF或扁平图片图纸需要先OCR或矢量化。",
            ],
            "skipped_count": len(skipped),
        },
        "documents": docs,
        "skipped": skipped,
        "connection_count": len(all_connections),
    }

    (output_dir / "pid_topology_index.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    write_connections_csv(output_dir / "pid_topology_connections.csv", all_connections)
    (output_dir / "pid_topology_review.md").write_text(render_markdown(package, all_connections), encoding="utf-8")

    print(f"Wrote topology evidence to: {output_dir}")
    print(f"PDFs inspected: {len(docs)}; candidate connections: {len(all_connections)}")
    print(f"PDFs skipped by default filters: {len(skipped)}")
    return 0


def is_probable_flow_drawing(path: Path) -> bool:
    name = path.name.lower()
    tokens = ("p&id", "pid", "管道及仪表流程图", "管道仪表流程图")
    return any(token in name for token in tokens)


def is_pfd_context_drawing(path: Path) -> bool:
    name = path.name.lower()
    if "p&id" in name or "pid" in name or "管道及仪表" in path.name or "管道仪表" in path.name:
        return False
    return "pfd" in name or "工艺流程图" in path.name


def is_existing_drawing(path: Path) -> bool:
    return "已建" in str(path)


def is_standard_reference_drawing(path: Path) -> bool:
    name = path.name
    tokens = ("通用注释", "通用图例", "通用管道详图", "通用仪表详图", "通用仪表缩写", "取样详图")
    return any(token in name for token in tokens)


def analyze_pdf(
    path: Path,
    input_dir: Path,
    page_limit: int,
    min_line_length: float,
    join_tolerance: float,
    snap_distance: float,
    max_connections_per_component: int,
) -> dict[str, Any]:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        raise SystemExit("PyMuPDF is required. Install with: py -m pip install --user PyMuPDF") from exc

    rel_path = str(path.relative_to(input_dir))
    result = {
        "rel_path": rel_path,
        "size_bytes": path.stat().st_size,
        "pages": [],
        "warnings": [],
    }
    try:
        doc = fitz.open(path)
    except Exception as exc:
        result["warnings"].append(f"open_failed:{type(exc).__name__}:{exc}")
        return result

    page_count = len(doc)
    max_pages = page_count if page_limit <= 0 else min(page_count, page_limit)
    if max_pages < page_count:
        result["warnings"].append(f"truncated_pages:{max_pages}_of_{page_count}")

    for page_index in range(max_pages):
        page = doc[page_index]
        text_candidates = extract_text_candidates(page, page_index + 1)
        segments = extract_segments(page, page_index + 1, min_line_length)
        components = build_components(
            segments=segments,
            text_candidates=text_candidates,
            join_tolerance=join_tolerance,
            snap_distance=snap_distance,
            max_connections_per_component=max_connections_per_component,
        )
        result["pages"].append({
            "page": page_index + 1,
            "width": float(page.rect.width),
            "height": float(page.rect.height),
            "text_candidate_count": len(text_candidates),
            "tag_count": len([t for t in text_candidates if t.kind == "tag"]),
            "line_id_count": len([t for t in text_candidates if t.kind == "line_id"]),
            "segment_count": len(segments),
            "component_count": len(components),
            "candidates_sample": [dataclasses.asdict(t) for t in text_candidates[:80]],
            "components": [dataclasses.asdict(c) for c in components],
        })
    doc.close()
    return result


def extract_text_candidates(page: Any, page_number: int) -> list[TextCandidate]:
    candidates: list[TextCandidate] = []
    data = page.get_text("dict")
    seen: set[tuple[str, str, int, int]] = set()
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = normalize_text(span.get("text", ""))
                if not text:
                    continue
                bbox = tuple(float(v) for v in span.get("bbox", (0, 0, 0, 0)))
                for kind, pattern in (("tag", TAG_RE), ("line_id", LINE_ID_RE)):
                    for match in pattern.finditer(text):
                        value = normalize_tag(match.group(0)) if kind == "tag" else match.group(0).upper()
                        key = (value, kind, int(bbox[0]), int(bbox[1]))
                        if key in seen:
                            continue
                        seen.add(key)
                        candidates.append(TextCandidate(value, kind, page_number, bbox))
    return candidates


def extract_segments(page: Any, page_number: int, min_line_length: float) -> list[Segment]:
    segments: list[Segment] = []
    drawings = page.get_drawings()
    serial = 0
    for drawing in drawings:
        for item in drawing.get("items", []):
            op = item[0]
            if op == "l":
                raw_pairs = [(item[1], item[2])]
            elif op == "re":
                rect = item[1]
                raw_pairs = [
                    ((rect.x0, rect.y0), (rect.x1, rect.y0)),
                    ((rect.x1, rect.y0), (rect.x1, rect.y1)),
                    ((rect.x1, rect.y1), (rect.x0, rect.y1)),
                    ((rect.x0, rect.y1), (rect.x0, rect.y0)),
                ]
            else:
                continue
            for p1, p2 in raw_pairs:
                x1, y1 = point_xy(p1)
                x2, y2 = point_xy(p2)
                length = math.hypot(x2 - x1, y2 - y1)
                if length < min_line_length:
                    continue
                orientation = classify_orientation(x1, y1, x2, y2)
                serial += 1
                segments.append(Segment(
                    segment_id=f"S{page_number:02d}-{serial:05d}",
                    page=page_number,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    length=round(length, 2),
                    orientation=orientation,
                ))
    return segments


def point_xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def classify_orientation(x1: float, y1: float, x2: float, y2: float) -> str:
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dy <= 2.0 and dx > dy:
        return "horizontal"
    if dx <= 2.0 and dy > dx:
        return "vertical"
    return "diagonal"


def build_components(
    segments: list[Segment],
    text_candidates: list[TextCandidate],
    join_tolerance: float,
    snap_distance: float,
    max_connections_per_component: int,
) -> list[Component]:
    if not segments:
        return []

    uf = UnionFind(len(segments))
    grid: dict[tuple[int, int], list[int]] = {}
    for index, segment in enumerate(segments):
        for x, y in ((segment.x1, segment.y1), (segment.x2, segment.y2)):
            cell = (round(x / join_tolerance), round(y / join_tolerance))
            for neighbor in neighbor_cells(cell):
                for other_index in grid.get(neighbor, []):
                    other = segments[other_index]
                    if endpoints_close((x, y), other, join_tolerance):
                        uf.union(index, other_index)
            grid.setdefault(cell, []).append(index)

    grouped: dict[int, list[Segment]] = {}
    for index, segment in enumerate(segments):
        grouped.setdefault(uf.find(index), []).append(segment)

    components: list[Component] = []
    for component_index, component_segments in enumerate(grouped.values(), start=1):
        bbox = segments_bbox(component_segments)
        orientation = dominant_orientation(component_segments)
        associated = associate_text(component_segments, text_candidates, snap_distance)
        connections = build_candidate_connections(
            associated,
            component_segments,
            max_connections_per_component,
            snap_distance,
        )
        if not associated and len(component_segments) < 3:
            continue
        components.append(Component(
            component_id=f"C{component_segments[0].page:02d}-{component_index:04d}",
            page=component_segments[0].page,
            segment_ids=[s.segment_id for s in component_segments[:120]],
            bbox=tuple(round(v, 2) for v in bbox),
            orientation=orientation,
            associated_text=associated,
            connections=connections,
        ))
    components.sort(key=lambda c: (-len(c.connections), -len(c.associated_text), c.component_id))
    return components[:120]


def neighbor_cells(cell: tuple[int, int]) -> Iterable[tuple[int, int]]:
    x, y = cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            yield x + dx, y + dy


def endpoints_close(point: tuple[float, float], segment: Segment, tolerance: float) -> bool:
    px, py = point
    return (
        math.hypot(px - segment.x1, py - segment.y1) <= tolerance
        or math.hypot(px - segment.x2, py - segment.y2) <= tolerance
    )


def segments_bbox(segments: list[Segment]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for segment in segments:
        xs.extend([segment.x1, segment.x2])
        ys.extend([segment.y1, segment.y2])
    return min(xs), min(ys), max(xs), max(ys)


def dominant_orientation(segments: list[Segment]) -> str:
    totals = {"horizontal": 0.0, "vertical": 0.0, "diagonal": 0.0}
    for segment in segments:
        totals[segment.orientation] += segment.length
    return max(totals.items(), key=lambda item: item[1])[0]


def associate_text(
    segments: list[Segment],
    text_candidates: list[TextCandidate],
    snap_distance: float,
) -> list[dict[str, Any]]:
    associated: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in text_candidates:
        center = bbox_center(candidate.bbox)
        nearest_segment = None
        nearest_distance = float("inf")
        for segment in segments:
            distance = distance_point_to_segment(center[0], center[1], segment)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_segment = segment
        if nearest_segment is None or nearest_distance > snap_distance:
            continue
        key = (candidate.kind, candidate.text)
        if key in seen:
            continue
        seen.add(key)
        associated.append({
            "text": candidate.text,
            "kind": candidate.kind,
            "page": candidate.page,
            "bbox": tuple(round(v, 2) for v in candidate.bbox),
            "center": tuple(round(v, 2) for v in center),
            "nearest_segment": nearest_segment.segment_id,
            "distance": round(nearest_distance, 2),
        })
    associated.sort(key=lambda item: (item["kind"], item["distance"], item["text"]))
    return associated[:40]


def build_candidate_connections(
    associated: list[dict[str, Any]],
    segments: list[Segment],
    max_connections: int,
    snap_distance: float,
) -> list[dict[str, Any]]:
    tags = [item for item in associated if item["kind"] == "tag"]
    if len(tags) < 2:
        return []
    orientation = dominant_orientation(segments)
    if orientation == "vertical":
        tags.sort(key=lambda item: (item["center"][1], item["center"][0], item["text"]))
    else:
        tags.sort(key=lambda item: (item["center"][0], item["center"][1], item["text"]))

    connections: list[dict[str, Any]] = []
    for left, right in zip(tags, tags[1:]):
        if left["text"] == right["text"]:
            continue
        confidence = "high" if max(left["distance"], right["distance"]) <= snap_distance / 2 else "medium"
        connections.append({
            "from": left["text"],
            "to": right["text"],
            "confidence": confidence,
            "reason": "同一矢量线段组件；按图纸坐标排序的相邻关联位号",
            "from_distance": left["distance"],
            "to_distance": right["distance"],
            "component_orientation": orientation,
        })
        if len(connections) >= max_connections:
            break
    return connections


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def distance_point_to_segment(px: float, py: float, segment: Segment) -> float:
    x1, y1, x2, y2 = segment.x1, segment.y1, segment.x2, segment.y2
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def write_connections_csv(path: Path, connections: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "rel_path", "page", "component_id", "from", "to", "confidence", "reason",
            "from_distance", "to_distance", "component_orientation",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in connections:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def render_markdown(package: dict[str, Any], connections: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# P&ID图纸拓扑证据抽取报告")
    lines.append("")
    lines.append(f"- 生成时间：{package['metadata']['generated_at']}")
    lines.append(f"- 输入目录：`{package['metadata']['input_dir']}`")
    lines.append(f"- PDF数量：{len(package['documents'])}")
    lines.append(f"- 默认过滤跳过：{package['metadata'].get('skipped_count', 0)}")
    lines.append(f"- 候选连接数：{len(connections)}")
    lines.append("")
    lines.append("## 方法边界")
    lines.append("")
    for item in package["metadata"]["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("本报告不是最终工艺拓扑。它只说明：哪些位号在矢量PDF中靠近同一组线段，因此值得专家人工看图核查。")
    lines.append("")
    lines.append("## 候选连接总表")
    lines.append("")
    lines.append("| 图纸 | 页 | 组件 | From | To | 置信度 | 依据 |")
    lines.append("| --- | ---: | --- | --- | --- | --- | --- |")
    for row in connections[:300]:
        lines.append(
            f"| `{escape_pipe(row['rel_path'])}` | {row['page']} | {row['component_id']} | "
            f"{escape_pipe(row['from'])} | {escape_pipe(row['to'])} | {CONFIDENCE_LABEL.get(row['confidence'], row['confidence'])} | {escape_pipe(row['reason'])} |"
        )
    if len(connections) > 300:
        lines.append(f"| ... | ... | ... | ... | ... | ... | 另有 {len(connections) - 300} 条见 CSV/JSON |")
    lines.append("")
    lines.append("## 逐图纸证据")
    lines.append("")
    for doc in package["documents"]:
        lines.append(f"### {doc['rel_path']}")
        if doc.get("warnings"):
            lines.append("")
            lines.append("- 警告：" + "；".join(doc["warnings"]))
        for page in doc.get("pages", []):
            connection_count = sum(len(component["connections"]) for component in page["components"])
            lines.append("")
            lines.append(
                f"- 第 {page['page']} 页：文本候选 {page['text_candidate_count']}，位号 {page['tag_count']}，"
                f"管线号 {page['line_id_count']}，矢量线段 {page['segment_count']}，线段组件 {page['component_count']}，候选连接 {connection_count}"
            )
            useful_components = [c for c in page["components"] if c["connections"]][:8]
            for component in useful_components:
                associated = ", ".join(item["text"] for item in component["associated_text"][:10])
                lines.append(f"  - `{component['component_id']}` {component['orientation']}：{associated}")
                for connection in component["connections"][:8]:
                    lines.append(
                        f"    - {connection['from']} -> {connection['to']} "
                        f"({CONFIDENCE_LABEL.get(connection['confidence'], connection['confidence'])}，距离={connection['from_distance']}/{connection['to_distance']})"
                    )
        lines.append("")
    return "\n".join(lines) + "\n"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_tag(tag: str) -> str:
    return re.sub(r"\s+", "-", tag.upper())


def escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
