#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a human-facing HAZOP pre-review workbench.

This dashboard merges drawing-by-drawing expert prompts from
hazop_expert_opinions.json with vector-PDF topology evidence from
pid_topology_index.json. The goal is not to prove final process topology, but
to give a participating expert a useful meeting-prep surface.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 9}
PRIORITY_LABEL = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
    "none": "待看图",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_script_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("</", "<\\/")


def is_probably_garbled(text: str) -> bool:
    if not text:
        return True
    stripped = re.sub(r"\s+", "", text)
    if len(stripped) < 8:
        return True
    bad = 0
    useful = 0
    for ch in stripped:
        code = ord(ch)
        category = unicodedata.category(ch)
        if ch == "\ufffd" or category.startswith("C") or 0xE000 <= code <= 0xF8FF:
            bad += 1
            continue
        if (
            "\u4e00" <= ch <= "\u9fff"
            or "A" <= ch <= "Z"
            or "a" <= ch <= "z"
            or "0" <= ch <= "9"
            or ch in "-_/#&+.%()[]（）℃°\"'~，。；：、"
        ):
            useful += 1
    if bad / max(len(stripped), 1) > 0.03:
        return True
    if useful / max(len(stripped), 1) < 0.62:
        return True
    repeated_symbols = len(re.findall(r"[^A-Za-z0-9\u4e00-\u9fff\s]{5,}", stripped))
    return repeated_symbols > 6


def clean_excerpt(text: str, limit: int = 260) -> tuple[str, bool]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if is_probably_garbled(compact):
        return "", False
    if len(compact) > limit:
        compact = compact[:limit].rstrip() + "..."
    return compact, True


def norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().lower()


def basename_key(value: Any) -> str:
    return Path(str(value or "").replace("\\", "/")).name.lower()


def compact_evidence(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    evidence = []
    for item in items[:limit]:
        excerpt, usable = clean_excerpt(str(item.get("excerpt", "")))
        evidence.append({
            "relPath": item.get("rel_path", ""),
            "keyword": item.get("keyword", ""),
            "excerpt": excerpt,
            "usable": usable,
            "tags": item.get("tags", []),
        })
    return evidence


def compact_finding(finding: dict[str, Any]) -> dict[str, Any]:
    priority = finding.get("priority") or "low"
    fields = [
        finding.get("finding_id", ""),
        priority,
        finding.get("parameter", ""),
        finding.get("analysis_object", ""),
        finding.get("problem", ""),
        " ".join(str(x) for x in finding.get("guidewords", [])),
        " ".join(str(x) for x in finding.get("possible_causes", [])),
        " ".join(str(x) for x in finding.get("possible_consequences", [])),
        " ".join(str(x) for x in finding.get("existing_safeguards_to_verify", [])),
        " ".join(str(x) for x in finding.get("expert_actions", [])),
        " ".join(str(x) for x in finding.get("related_documents", [])),
        " ".join(str(x.get("excerpt", "")) for x in finding.get("evidence", []) if isinstance(x, dict)),
    ]
    return {
        "id": finding.get("finding_id", ""),
        "priority": priority,
        "priorityLabel": PRIORITY_LABEL.get(priority, priority),
        "confidence": finding.get("confidence", ""),
        "parameter": finding.get("parameter", ""),
        "guidewords": finding.get("guidewords", []),
        "analysisObject": finding.get("analysis_object", ""),
        "problem": finding.get("problem", ""),
        "causes": finding.get("possible_causes", []),
        "consequences": finding.get("possible_consequences", []),
        "safeguards": finding.get("existing_safeguards_to_verify", []),
        "actions": finding.get("expert_actions", []),
        "evidence": compact_evidence(finding.get("evidence", [])),
        "relatedDocs": finding.get("related_documents", []),
        "sourceRule": finding.get("source_rule", ""),
        "searchText": " ".join(str(x) for x in fields).lower(),
    }


def compact_topology_component(page: dict[str, Any], component: dict[str, Any]) -> dict[str, Any]:
    connections = component.get("connections", [])
    associated = component.get("associated_text", [])
    high_count = sum(1 for item in connections if item.get("confidence") == "high")
    return {
        "page": page.get("page", 0),
        "componentId": component.get("component_id", ""),
        "orientation": component.get("orientation", ""),
        "bbox": component.get("bbox", []),
        "highCount": high_count,
        "connectionCount": len(connections),
        "connections": connections[:8],
        "associatedText": associated[:14],
    }


def build_topology_maps(topology: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, int]]:
    by_rel: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    summary = {
        "topologyDocuments": len(topology.get("documents", [])),
        "skippedTopologyDocuments": len(topology.get("skipped", [])),
        "topologyConnections": int(topology.get("connection_count") or 0),
        "highTopologyConnections": 0,
    }
    for doc in topology.get("documents", []):
        components = []
        tags: set[str] = set()
        segment_count = 0
        component_count = 0
        connection_count = 0
        high_count = 0
        for page in doc.get("pages", []):
            segment_count += int(page.get("segment_count") or 0)
            component_count += int(page.get("component_count") or 0)
            for component in page.get("components", []):
                connections = component.get("connections", [])
                if not connections:
                    continue
                connection_count += len(connections)
                high_count += sum(1 for item in connections if item.get("confidence") == "high")
                for item in connections:
                    if item.get("from"):
                        tags.add(str(item.get("from")))
                    if item.get("to"):
                        tags.add(str(item.get("to")))
                for item in component.get("associated_text", []):
                    if item.get("text"):
                        tags.add(str(item.get("text")))
                components.append(compact_topology_component(page, component))
        summary["highTopologyConnections"] += high_count
        components.sort(key=lambda item: (-item["highCount"], -item["connectionCount"], item["componentId"]))
        compact = {
            "relPath": doc.get("rel_path", ""),
            "warnings": doc.get("warnings", []),
            "pageCount": len(doc.get("pages", [])),
            "segmentCount": segment_count,
            "componentCount": component_count,
            "connectionCount": connection_count,
            "highConnectionCount": high_count,
            "tags": sorted(tags)[:80],
            "components": components[:18],
            "searchText": " ".join([str(doc.get("rel_path", "")), " ".join(sorted(tags))]).lower(),
        }
        by_rel[norm_path(doc.get("rel_path", ""))] = compact
        by_name[basename_key(doc.get("rel_path", ""))] = compact
    return by_rel, by_name, summary


def match_topology(review: dict[str, Any], by_rel: dict[str, dict[str, Any]], by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    rel = review.get("rel_path", "")
    return by_rel.get(norm_path(rel)) or by_name.get(basename_key(rel))


def find_source_file(design_root: Path | None, rel_path: str) -> Path | None:
    if not design_root or not rel_path:
        return None
    direct = design_root / rel_path
    if direct.exists():
        return direct
    target_name = basename_key(rel_path)
    matches = [path for path in design_root.rglob(Path(rel_path).name) if path.is_file()]
    if matches:
        return matches[0]
    for path in design_root.rglob("*.pdf"):
        if path.name.lower() == target_name:
            return path
    return None


def render_pdf_preview(path: Path, scale: float) -> dict[str, Any]:
    try:
        import fitz  # type: ignore
    except Exception:
        return {"error": "PyMuPDF not available"}

    try:
        doc = fitz.open(path)
        if len(doc) == 0:
            doc.close()
            return {"error": "empty pdf"}
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        data_uri = "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode("ascii")
        preview = {
            "dataUri": data_uri,
            "page": 1,
            "pageWidth": float(page.rect.width),
            "pageHeight": float(page.rect.height),
            "imageWidth": int(pix.width),
            "imageHeight": int(pix.height),
        }
        doc.close()
        return preview
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def build_preview_maps(
    reviews: list[dict[str, Any]],
    design_root: Path | None,
    preview_scale: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    by_rel: dict[str, dict[str, Any]] = {}
    rendered = 0
    failed = 0
    for review in reviews:
        rel_path = str(review.get("rel_path", ""))
        if not rel_path.lower().endswith(".pdf"):
            continue
        key = norm_path(rel_path)
        if key in by_rel:
            continue
        source = find_source_file(design_root, rel_path)
        if not source:
            failed += 1
            by_rel[key] = {"error": "source pdf not found"}
            continue
        preview = render_pdf_preview(source, preview_scale)
        if preview.get("dataUri"):
            rendered += 1
        else:
            failed += 1
        by_rel[key] = preview
    return by_rel, {"previewRendered": rendered, "previewFailed": failed}


def topology_advice(topology: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not topology or not topology.get("components"):
        return []

    advice: list[dict[str, Any]] = []
    for component in topology.get("components", [])[:6]:
        connections = component.get("connections", [])
        if not connections:
            continue
        path = "，".join(
            f"{item.get('from', '')}->{item.get('to', '')}"
            for item in connections[:4]
            if item.get("from") or item.get("to")
        )
        tags = {
            str(item.get("from", "")).upper()
            for item in connections
            if item.get("from")
        } | {
            str(item.get("to", "")).upper()
            for item in connections
            if item.get("to")
        }
        tag_text = "、".join(sorted(tags)[:8])
        questions = [
            f"请设计方在本图上确认候选连通关系 {path} 是否真实成立；若成立，说明正常流向、切断边界和跨图去向；若不成立，标记为抽取误差。",
        ]
        if any(tag.startswith(("TK", "T-C", "C07", "C-07")) for tag in tags):
            questions.append("围绕储罐/罐区连接，核查进液、出液、BOG、回流/保冷循环路径是否在本图闭合，并确认高高液位、压力/真空保护的触发去向。")
        if any(tag.startswith(("P", "P-", "C08", "C09")) for tag in tags):
            questions.append("围绕泵或输送路径，核查吸入口/出口隔离、最小流量或回流、低低液位停泵、泵跳车后下游压力/流量偏差。")
        if any(tag.startswith(("LT", "LIT", "LIC", "PT", "PIT", "PIC", "FT", "FIT", "FIC", "FC", "PC", "LC")) for tag in tags):
            questions.append("围绕仪表点，核查取源点、信号去向、报警/联锁编号、C&E矩阵和图中阀门动作是否能一一追溯。")
        if any(tag.startswith(("MOV", "XV", "SDV", "ESDV", "BDV", "PCV", "LCV", "FCV", "PSV", "PRV", "TSV")) for tag in tags):
            questions.append("围绕阀门/泄放件，核查常开常关、故障位、旁路、隔离后封闭液段热膨胀泄放和排放去向。")
        advice.append({
            "componentId": component.get("componentId", ""),
            "page": component.get("page", 1),
            "bbox": component.get("bbox", []),
            "tags": tag_text,
            "basis": f"同一矢量线段组件，{len(connections)} 条候选连接；组件方向 {component.get('orientation', '')}",
            "connections": connections[:6],
            "questions": questions,
        })
    return advice


def compact_review(
    review: dict[str, Any],
    topology: dict[str, Any] | None,
    preview: dict[str, Any] | None,
) -> dict[str, Any]:
    findings = [compact_finding(item) for item in review.get("findings", [])]
    findings.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 9), item["id"]))
    if topology and findings:
        tags = set(str(tag).upper() for tag in topology.get("tags", []))

        def finding_score(item: dict[str, Any]) -> tuple[int, int, str]:
            text = " ".join([
                str(item.get("analysisObject", "")),
                str(item.get("problem", "")),
                " ".join(str(tag) for ev in item.get("evidence", []) for tag in ev.get("tags", [])),
            ]).upper()
            overlap = sum(1 for tag in tags if tag and tag in text)
            return (-overlap, PRIORITY_ORDER.get(item["priority"], 9), item["id"])

        findings = sorted(findings, key=finding_score)[:5]
    elif findings:
        findings = findings[:5]
    worst_priority = findings[0]["priority"] if findings else "none"
    advice = topology_advice(topology)
    search_fields = [
        review.get("drawing_id", ""),
        review.get("drawing_no", ""),
        review.get("rel_path", ""),
        review.get("title", ""),
        review.get("node_hint", ""),
        review.get("design_intent_hint", ""),
        " ".join(str(x) for x in review.get("review_focus", [])),
        " ".join(item["searchText"] for item in findings),
        " ".join(" ".join(item.get("questions", [])) for item in advice),
        topology.get("searchText", "") if topology else "",
    ]
    return {
        "drawingId": review.get("drawing_id", ""),
        "drawingNo": review.get("drawing_no", ""),
        "relPath": review.get("rel_path", ""),
        "title": review.get("title", ""),
        "docTypes": review.get("doc_types", []),
        "textChars": review.get("text_chars", 0),
        "warnings": review.get("extraction_warnings", []),
        "nodeHint": review.get("node_hint", ""),
        "designIntentHint": review.get("design_intent_hint", ""),
        "reviewFocus": review.get("review_focus", []),
        "findings": findings,
        "worstPriority": worst_priority,
        "worstPriorityLabel": PRIORITY_LABEL.get(worst_priority, worst_priority),
        "hasTopology": bool(topology and topology.get("connectionCount")),
        "topology": topology,
        "topologyAdvice": advice,
        "preview": preview or {},
        "searchText": " ".join(str(x) for x in search_fields).lower(),
    }


def build_workbench(
    hazop: dict[str, Any],
    topology: dict[str, Any],
    design_root: Path | None,
    preview_scale: float,
) -> dict[str, Any]:
    by_rel, by_name, topo_summary = build_topology_maps(topology)
    raw_reviews = hazop.get("drawing_reviews", [])
    preview_map, preview_summary = build_preview_maps(raw_reviews, design_root, preview_scale)
    reviews = []
    for review in raw_reviews:
        preview = preview_map.get(norm_path(review.get("rel_path", "")))
        reviews.append(compact_review(review, match_topology(review, by_rel, by_name), preview))

    reviews.sort(key=lambda item: (
        PRIORITY_ORDER.get(item["worstPriority"], 9),
        0 if item["hasTopology"] else 1,
        item["drawingNo"] or item["drawingId"],
    ))

    priority_counts = Counter(
        finding["priority"]
        for review in reviews
        for finding in review["findings"]
    )
    finding_count = sum(len(review["findings"]) for review in reviews)
    matched_topology = sum(1 for review in reviews if review["hasTopology"])
    matched_connections = sum(
        int(review["topology"].get("connectionCount") or 0)
        for review in reviews
        if review["topology"]
    )

    return {
        "metadata": hazop.get("metadata", {}),
        "signals": hazop.get("signals", []),
        "projectContext": hazop.get("project_context", {}),
        "summary": {
            "drawingCount": len(reviews),
            "findingCount": finding_count,
            "criticalHighCount": priority_counts.get("critical", 0) + priority_counts.get("high", 0),
            "matchedTopologyDrawings": matched_topology,
            "matchedTopologyConnections": matched_connections,
            **topo_summary,
            **preview_summary,
            "pfdContextCount": len(hazop.get("project_context", {}).get("pfd_context_documents", [])),
            "ignoredExistingCount": len(hazop.get("project_context", {}).get("ignored_existing_drawings", [])),
            "ignoredReferenceCount": len(hazop.get("project_context", {}).get("ignored_reference_drawings", [])),
            "priorityCounts": dict(priority_counts),
        },
        "reviews": reviews,
    }


def stat_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("P&ID图纸", summary.get("drawingCount", 0), "neutral"),
        ("问题行", summary.get("findingCount", 0), "accent"),
        ("关键/高", summary.get("criticalHighCount", 0), "hot"),
        ("原图预览", summary.get("previewRendered", 0), "green"),
        ("拓扑连接", summary.get("matchedTopologyConnections", 0), "blue"),
    ]
    return "\n".join(
        f'<div class="stat {cls}"><b>{esc(value)}</b><span>{esc(label)}</span></div>'
        for label, value, cls in cards
    )


def render_html(data: dict[str, Any]) -> str:
    metadata = data.get("metadata", {})
    summary = data.get("summary", {})
    signal_items = "".join(f'<span class="chip">{esc(item)}</span>' for item in data.get("signals", []))
    priority_counts = summary.get("priorityCounts", {})
    priority_items = "".join(
        f'<span class="chip {key}">{esc(PRIORITY_LABEL.get(key, key))} <b>{esc(priority_counts.get(key, 0))}</b></span>'
        for key in ["critical", "high", "medium", "low"]
    )
    html_text = HTML_TEMPLATE
    replacements = {
        "__PROJECT__": esc(metadata.get("project_name", "HAZOP预审")),
        "__GENERATED_AT__": esc(metadata.get("generated_at", "")),
        "__STAT_CARDS__": stat_cards(summary),
        "__SIGNAL_ITEMS__": signal_items or '<span class="chip">未识别明显项目信号</span>',
        "__PRIORITY_ITEMS__": priority_items,
        "__TOPO_TOTAL__": esc(summary.get("topologyConnections", 0)),
        "__TOPO_HIGH__": esc(summary.get("highTopologyConnections", 0)),
        "__TOPO_SKIPPED__": esc(summary.get("skippedTopologyDocuments", 0)),
        "__PREVIEW_FAILED__": esc(summary.get("previewFailed", 0)),
        "__PFD_CONTEXT__": esc(summary.get("pfdContextCount", 0)),
        "__IGNORED_EXISTING__": esc(summary.get("ignoredExistingCount", 0)),
        "__IGNORED_REFERENCE__": esc(summary.get("ignoredReferenceCount", 0)),
        "__DATA__": safe_script_json(data),
    }
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    return html_text


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI-HAZOP 专家预审工作台</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #fff;
      --text: #1d2939;
      --muted: #667085;
      --border: #d9dee7;
      --accent: #006d77;
      --critical: #b42318;
      --high: #b54708;
      --medium: #175cd3;
      --low: #475467;
      --green: #067647;
      --blue: #175cd3;
      --soft: #f9fafb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 10;
      background: #fff;
      border-bottom: 1px solid var(--border);
      padding: 18px 28px 14px;
    }
    h1 { margin: 0 0 8px; font-size: 23px; letter-spacing: 0; }
    .subhead {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      color: var(--muted);
      font-size: 13px;
    }
    main {
      max-width: 1560px;
      margin: 0 auto;
      padding: 18px 28px 42px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .stat, .panel, .drawing {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .stat { padding: 14px; border-left: 5px solid var(--muted); }
    .stat.accent { border-left-color: var(--accent); }
    .stat.hot { border-left-color: var(--high); }
    .stat.green { border-left-color: var(--green); }
    .stat.blue { border-left-color: var(--blue); }
    .stat b { display: block; font-size: 28px; line-height: 1; }
    .stat span { display: block; margin-top: 7px; color: var(--muted); font-size: 13px; }
    .panel { padding: 14px 16px; margin-bottom: 14px; }
    .panel h2 { margin: 0 0 10px; font-size: 16px; }
    .chips { display: flex; flex-wrap: wrap; gap: 7px; }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 4px 8px;
      background: #fff;
      color: #344054;
      font-size: 12px;
    }
    .chip.critical { border-color: #f0b8b2; color: var(--critical); }
    .chip.high { border-color: #efc27b; color: var(--high); }
    .chip.medium { border-color: #adc8f5; color: var(--medium); }
    .chip.low { color: var(--low); }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto;
      gap: 12px;
      margin: 14px 0;
      align-items: center;
    }
    input[type="search"] {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 15px;
      background: #fff;
    }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
    button {
      border: 1px solid var(--border);
      background: #fff;
      color: #344054;
      border-radius: 8px;
      padding: 9px 12px;
      cursor: pointer;
      font-size: 14px;
    }
    button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .drawing { margin-bottom: 12px; overflow: hidden; }
    .drawing-head {
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 13px 15px;
      cursor: pointer;
      border-left: 6px solid var(--border);
      background: #fbfcfe;
    }
    .drawing[data-priority="critical"] .drawing-head { border-left-color: var(--critical); }
    .drawing[data-priority="high"] .drawing-head { border-left-color: var(--high); }
    .drawing[data-priority="medium"] .drawing-head { border-left-color: var(--medium); }
    .drawing[data-priority="low"] .drawing-head { border-left-color: var(--low); }
    .badge {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-width: 72px;
      border-radius: 999px;
      padding: 5px 8px;
      color: #fff;
      font-size: 13px;
      font-weight: 700;
      background: var(--low);
    }
    .badge.critical { background: var(--critical); }
    .badge.high { background: var(--high); }
    .badge.medium { background: var(--medium); }
    .badge.low { background: var(--low); }
    .badge.none { background: #98a2b3; }
    .drawing-title strong { display: block; font-size: 16px; overflow-wrap: anywhere; }
    .drawing-title span { display: block; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    .counts { display: flex; gap: 7px; flex-wrap: wrap; justify-content: flex-end; }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 4px 8px;
      background: #fff;
      color: #344054;
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.topology { border-color: #9bd2c7; color: var(--green); }
    .drawing-body {
      display: none;
      padding: 15px;
      border-top: 1px solid var(--border);
      background: #fff;
    }
    .drawing.open .drawing-body { display: block; }
    .review-layout {
      display: grid;
      grid-template-columns: minmax(420px, 1.05fr) minmax(420px, 0.95fr);
      gap: 14px;
      align-items: start;
    }
    .visual-panel, .advice-panel {
      min-width: 0;
    }
    .visual-panel {
      position: sticky;
      top: 116px;
    }
    .drawing-preview {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      margin-bottom: 12px;
    }
    .drawing-preview h3 {
      margin: 0;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      font-size: 14px;
      color: #344054;
      background: #fbfcfe;
    }
    .preview-scroll {
      max-height: 720px;
      overflow: auto;
      background: #f2f4f7;
    }
    .preview-svg {
      display: block;
      width: 100%;
      min-width: 720px;
      height: auto;
    }
    .topo-rect {
      fill: rgba(6, 118, 71, 0.08);
      stroke: #067647;
      stroke-width: 5;
      vector-effect: non-scaling-stroke;
    }
    .topo-rect.medium {
      fill: rgba(181, 71, 8, 0.08);
      stroke: #b54708;
    }
    .topo-label {
      font-size: 30px;
      fill: #067647;
      paint-order: stroke;
      stroke: #fff;
      stroke-width: 5px;
      stroke-linejoin: round;
    }
    .advice-card {
      border: 1px solid #cfe8e4;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 10px;
      background: #f4fbfa;
    }
    .advice-card h3 {
      margin: 0 0 6px;
      font-size: 14px;
      color: #184e4f;
    }
    .advice-card ul {
      margin: 8px 0 0;
      padding-left: 18px;
      font-size: 13px;
    }
    .muted-note {
      color: var(--muted);
      font-size: 13px;
    }
    .brief {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .brief-block {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--soft);
      min-width: 0;
    }
    .brief-block b { display: block; margin-bottom: 5px; font-size: 13px; color: #344054; }
    .brief-block span { color: #344054; font-size: 13px; overflow-wrap: anywhere; }
    .finding {
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 12px;
      overflow: hidden;
    }
    .finding-head {
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      background: #fbfcfe;
    }
    .finding-head strong { overflow-wrap: anywhere; }
    .finding-body { padding: 12px; }
    .chain {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .chain-block {
      border: 1px solid #eaecf0;
      border-radius: 8px;
      padding: 10px;
      background: #fff;
    }
    .chain-block h4 { margin: 0 0 6px; font-size: 13px; color: #344054; }
    .chain-block ul { margin: 0; padding-left: 18px; font-size: 13px; }
    .chain-block li { margin-bottom: 5px; }
    .evidence {
      margin-top: 10px;
      border-top: 1px solid #eaecf0;
      padding-top: 10px;
    }
    details.evidence summary {
      cursor: pointer;
      color: #344054;
      font-size: 13px;
    }
    .evidence-item {
      border: 1px solid #eaecf0;
      border-radius: 8px;
      background: #fbfcfe;
      padding: 8px 10px;
      margin-top: 7px;
      font-size: 13px;
    }
    .evidence-title { font-weight: 700; color: #344054; overflow-wrap: anywhere; }
    .excerpt { margin-top: 5px; color: #344054; white-space: pre-wrap; }
    .topology-panel {
      border: 1px solid #cfe8e4;
      border-radius: 8px;
      padding: 12px;
      margin-top: 14px;
      background: #f4fbfa;
    }
    .topology-grid {
      display: grid;
      grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
      gap: 12px;
      align-items: start;
    }
    .topo-list { display: grid; gap: 8px; }
    .topo-component {
      border: 1px solid #cfe8e4;
      border-radius: 8px;
      background: #fff;
      padding: 9px 10px;
    }
    .topo-component b { display: block; font-size: 13px; margin-bottom: 6px; }
    .connection-row {
      display: grid;
      grid-template-columns: minmax(70px, 0.8fr) 22px minmax(70px, 0.8fr) 74px minmax(0, 1.4fr);
      gap: 6px;
      align-items: start;
      padding: 5px 0;
      border-top: 1px dashed #e4e7ec;
      font-size: 12px;
    }
    .connection-row:first-of-type { border-top: 0; }
    .empty {
      display: none;
      text-align: center;
      padding: 34px;
      color: var(--muted);
      background: #fff;
      border: 1px dashed var(--border);
      border-radius: 8px;
    }
    @media (max-width: 1080px) {
      header { position: static; }
      .stats, .toolbar, .drawing-head, .review-layout, .brief, .finding-head, .chain, .topology-grid {
        grid-template-columns: 1fr;
      }
      .visual-panel { position: static; }
      .counts, .filters { justify-content: flex-start; }
      .connection-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI-HAZOP 专家预审工作台</h1>
    <div class="subhead">
      <span>项目：__PROJECT__</span>
      <span>生成：__GENERATED_AT__</span>
      <span>角色：参会专家会前追问，不是主席结论</span>
    </div>
  </header>
  <main>
    <section class="stats">__STAT_CARDS__</section>

    <section class="panel">
      <h2>预审口径</h2>
      <div class="chips">
        __SIGNAL_ITEMS__
        __PRIORITY_ITEMS__
        <span class="chip">拓扑总连接 <b>__TOPO_TOTAL__</b></span>
        <span class="chip high">高置信拓扑 <b>__TOPO_HIGH__</b></span>
        <span class="chip low">默认跳过图纸 <b>__TOPO_SKIPPED__</b></span>
        <span class="chip low">原图未预览 <b>__PREVIEW_FAILED__</b></span>
        <span class="chip">PFD背景 <b>__PFD_CONTEXT__</b></span>
        <span class="chip low">已建忽略 <b>__IGNORED_EXISTING__</b></span>
        <span class="chip low">通用图忽略 <b>__IGNORED_REFERENCE__</b></span>
      </div>
      <p class="muted-note" style="margin:10px 0 0;">本页逐张分析对象为新建/扩建P&ID。PFD用于理解项目整体流程和边界；含“已建”的图纸默认作为既有装置接口背景，不进入本轮逐张问题行。</p>
    </section>

    <section class="toolbar">
      <input id="search" type="search" placeholder="搜索图纸、位号、问题、原因、后果、措施或拓扑连接，例如 C0804A / LT001 / ESD / BOG">
      <div class="filters">
        <button class="active" data-filter="all">全部</button>
        <button data-filter="critical-high">关键/高</button>
        <button data-filter="with-topology">有拓扑</button>
        <button data-filter="without-topology">需人工看图</button>
      </div>
    </section>

    <section id="drawing-list"></section>
    <div id="empty" class="empty">没有匹配的图纸或问题。</div>
  </main>

  <script id="workbench-data" type="application/json">__DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById('workbench-data').textContent);
    const list = document.getElementById('drawing-list');
    const empty = document.getElementById('empty');
    const search = document.getElementById('search');
    const buttons = [...document.querySelectorAll('button[data-filter]')];
    let activeFilter = 'all';

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function listItems(items) {
      const values = (items || []).filter(Boolean);
      if (!values.length) return '<ul><li>会上确认。</li></ul>';
      return '<ul>' + values.map(item => `<li>${escapeHtml(item)}</li>`).join('') + '</ul>';
    }

    function chipItems(items) {
      const values = (items || []).filter(Boolean);
      if (!values.length) return '<span class="chip">未识别</span>';
      return values.map(item => `<span class="chip">${escapeHtml(item)}</span>`).join('');
    }

    function confidenceLabel(value) {
      const labels = { high: '高', medium: '中', low: '低' };
      return labels[value] || value || '';
    }

    function reasonLabel(value) {
      if (value === 'same vector-line component; consecutive associated tags by drawing coordinate') {
        return '同一矢量线段组件；按图纸坐标排序的相邻关联位号';
      }
      return value || '';
    }

    function evidenceBlock(items) {
      const usable = (items || []).filter(item => item.usable && item.excerpt);
      if (!usable.length) return '<div class="evidence-item">文本抽取质量不足或无有效摘录，请以左侧原图和拓扑候选为准，会上要求设计方定位原图证据。</div>';
      return usable.map(item => `
        <div class="evidence-item">
          <div class="evidence-title">${escapeHtml(item.relPath)} · 关键词：${escapeHtml(item.keyword)}${item.tags?.length ? ' · tags: ' + escapeHtml(item.tags.join(', ')) : ''}</div>
          <div class="excerpt">${escapeHtml(item.excerpt)}</div>
        </div>
      `).join('');
    }

    function findingBlock(finding) {
      return `
        <section class="finding">
          <div class="finding-head">
            <span class="badge ${escapeHtml(finding.priority)}">${escapeHtml(finding.priorityLabel)}</span>
            <strong>${escapeHtml(finding.id)} · ${escapeHtml(finding.parameter)} · ${escapeHtml(finding.analysisObject)}</strong>
            <span class="pill">${escapeHtml(finding.sourceRule)}</span>
          </div>
          <div class="finding-body">
            <b>问题/偏差：</b>
            <div>${escapeHtml(finding.problem)}</div>
            <div class="chain">
              <div class="chain-block"><h4>可能原因</h4>${listItems(finding.causes)}</div>
              <div class="chain-block"><h4>可能后果</h4>${listItems(finding.consequences)}</div>
              <div class="chain-block"><h4>措施待核查</h4>${listItems(finding.safeguards)}</div>
              <div class="chain-block"><h4>会上追问</h4>${listItems(finding.actions)}</div>
            </div>
            ${finding.relatedDocs?.length ? `<div class="evidence"><b>必要时跨图核查：</b>${listItems(finding.relatedDocs)}</div>` : ''}
            <details class="evidence">
              <summary><b>本图纸文本证据</b></summary>
              ${evidenceBlock(finding.evidence)}
            </details>
          </div>
        </section>
      `;
    }

    function previewPanel(review) {
      const preview = review.preview || {};
      const topology = review.topology || {};
      if (!preview.dataUri) {
        return `
          <section class="drawing-preview">
            <h3>原设计图缩略图</h3>
            <div class="evidence-item">未能生成原图预览：${escapeHtml(preview.error || '未找到源PDF')}</div>
          </section>
        `;
      }
      const width = Number(preview.pageWidth) || 1000;
      const height = Number(preview.pageHeight) || 700;
      const rects = (topology.components || []).slice(0, 18).map(component => {
        const b = component.bbox || [0, 0, 0, 0];
        let x = Number(b[0]) || 0;
        let y = Number(b[1]) || 0;
        let w = Math.max(10, (Number(b[2]) || x) - x);
        let h = Math.max(10, (Number(b[3]) || y) - y);
        if (w === 10) x -= 5;
        if (h === 10) y -= 5;
        const cls = component.highCount ? 'topo-rect' : 'topo-rect medium';
        return `
          <rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}" />
          <text class="topo-label" x="${x}" y="${Math.max(28, y - 8)}">${escapeHtml(component.componentId)}</text>
        `;
      }).join('');
      return `
        <section class="drawing-preview">
          <h3>原设计图缩略图 + 候选拓扑框</h3>
          <div class="preview-scroll">
            <svg class="preview-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="原设计图缩略图">
              <image href="${preview.dataUri}" x="0" y="0" width="${width}" height="${height}" preserveAspectRatio="xMidYMid meet"></image>
              ${rects}
            </svg>
          </div>
        </section>
      `;
    }

    function topologyAdvicePanel(review) {
      const advice = review.topologyAdvice || [];
      if (!advice.length) {
        return `
          <section class="advice-card">
            <h3>本图拓扑追问</h3>
            <div class="muted-note">未形成可用拓扑追问。请先看左侧原图确认节点边界、前后连接、阀门状态和仪表回路。</div>
          </section>
        `;
      }
      return advice.map(item => `
        <section class="advice-card">
          <h3>第 ${escapeHtml(item.page)} 页 · ${escapeHtml(item.componentId)} · ${escapeHtml(item.tags || '候选连接')}</h3>
          <div class="muted-note">${escapeHtml(item.basis)}</div>
          ${listItems(item.questions)}
          <div class="chips" style="margin-top:8px;">
            ${(item.connections || []).slice(0, 6).map(connection => `<span class="chip">${escapeHtml(connection.from)} → ${escapeHtml(connection.to)} · ${escapeHtml(confidenceLabel(connection.confidence))}</span>`).join('')}
          </div>
        </section>
      `).join('');
    }

    function topologyPanel(topology) {
      if (!topology || !topology.connectionCount) {
        return `
          <section class="topology-panel">
            <b>拓扑证据：</b>未匹配到同名矢量拓扑结果。本图纸建议人工打开原图确认节点边界、前后连接、阀位和仪表回路。
          </section>
        `;
      }
      const tagChips = topology.tags.slice(0, 26).map(tag => `<span class="chip">${escapeHtml(tag)}</span>`).join('');
      const components = topology.components.slice(0, 10).map(component => `
        <div class="topo-component">
          <b>第 ${escapeHtml(component.page)} 页 · ${escapeHtml(component.componentId)} · ${escapeHtml(component.orientation)} · bbox ${escapeHtml((component.bbox || []).join(', '))}</b>
          ${component.connections.map(connection => `
            <div class="connection-row">
              <span>${escapeHtml(connection.from)}</span>
              <span>→</span>
              <span>${escapeHtml(connection.to)}</span>
              <span>${escapeHtml(confidenceLabel(connection.confidence))}</span>
              <span>${escapeHtml(reasonLabel(connection.reason))}</span>
            </div>
          `).join('')}
        </div>
      `).join('');
      return `
        <section class="topology-panel">
          <div class="brief">
            <div class="brief-block"><b>拓扑候选连接</b><span>${escapeHtml(topology.connectionCount)} 条，其中高置信 ${escapeHtml(topology.highConnectionCount)} 条</span></div>
            <div class="brief-block"><b>线段组件</b><span>${escapeHtml(topology.componentCount)} 个，线段 ${escapeHtml(topology.segmentCount)} 条</span></div>
            <div class="brief-block"><b>拓扑警告</b><span>${escapeHtml((topology.warnings || []).join('；') || '无')}</span></div>
          </div>
          <div class="topology-grid">
            <div><b>候选位号/文本</b><div class="chips" style="margin-top:8px;">${tagChips}</div></div>
            <div class="topo-list">${components}</div>
          </div>
        </section>
      `;
    }

    function drawingMatches(review, term) {
      if (activeFilter === 'critical-high' && !['critical', 'high'].includes(review.worstPriority)) return false;
      if (activeFilter === 'with-topology' && !review.hasTopology) return false;
      if (activeFilter === 'without-topology' && review.hasTopology) return false;
      if (!term) return true;
      return review.searchText.includes(term);
    }

    function drawingBlock(review, index) {
      return `
        <article class="drawing ${index === 0 ? 'open' : ''}" data-priority="${escapeHtml(review.worstPriority)}">
          <div class="drawing-head" role="button" tabindex="0">
            <span class="badge ${escapeHtml(review.worstPriority)}">${escapeHtml(review.worstPriorityLabel)}</span>
            <div class="drawing-title">
              <strong>${escapeHtml(review.drawingId)} · ${escapeHtml(review.drawingNo)} · ${escapeHtml(review.title)}</strong>
              <span>${escapeHtml(review.relPath)}</span>
            </div>
            <div class="counts">
              <span class="pill">${escapeHtml(review.findings.length)} 问题</span>
              <span class="pill topology">${escapeHtml(review.topology?.connectionCount || 0)} 拓扑连接</span>
              <span class="pill">${escapeHtml(review.textChars)} 字符</span>
            </div>
          </div>
          <div class="drawing-body">
            <div class="review-layout">
              <div class="visual-panel">
                ${previewPanel(review)}
                ${topologyPanel(review.topology)}
              </div>
              <div class="advice-panel">
                <div class="brief">
                  <div class="brief-block"><b>节点/对象提示</b><span>${escapeHtml(review.nodeHint || '需人工确认')}</span></div>
                  <div class="brief-block"><b>设计意图提示</b><span>${escapeHtml(review.designIntentHint || '需人工确认')}</span></div>
                  <div class="brief-block"><b>审查关注</b><div class="chips">${chipItems(review.reviewFocus)}</div></div>
                </div>
                ${review.warnings?.length ? `<div class="panel"><h2>抽取警告</h2>${listItems(review.warnings)}</div>` : ''}
                ${topologyAdvicePanel(review)}
                <div class="panel"><h2>本图规则提示</h2><div class="muted-note">仅保留与本图或本图拓扑位号最相关的前几条；文本摘录疑似乱码时默认隐藏。</div></div>
                ${review.findings.length ? review.findings.map(findingBlock).join('') : '<section class="finding"><div class="finding-body">本图纸未自动形成规则问题行，但仍需人工确认节点边界、阀门状态、跨图连接和联锁保护。</div></section>'}
              </div>
            </div>
          </div>
        </article>
      `;
    }

    function bindToggles() {
      document.querySelectorAll('.drawing-head').forEach(head => {
        head.addEventListener('click', () => head.closest('.drawing').classList.toggle('open'));
        head.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            head.closest('.drawing').classList.toggle('open');
          }
        });
      });
    }

    function render() {
      const term = search.value.trim().toLowerCase();
      const rows = data.reviews.filter(review => drawingMatches(review, term));
      list.innerHTML = rows.map(drawingBlock).join('');
      empty.style.display = rows.length ? 'none' : 'block';
      bindToggles();
    }

    buttons.forEach(button => {
      button.addEventListener('click', () => {
        buttons.forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        activeFilter = button.dataset.filter;
        render();
      });
    });
    search.addEventListener('input', render);
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an expert-facing AI-HAZOP workbench HTML.")
    parser.add_argument("--hazop-json", required=True, type=Path, help="hazop_expert_opinions.json")
    parser.add_argument("--topology-json", type=Path, help="topology/pid_topology_index.json")
    parser.add_argument("--design-root", type=Path, help="Original design package folder for rendering PDF previews.")
    parser.add_argument("--preview-scale", type=float, default=0.35, help="PDF preview render scale. Use lower values for smaller HTML.")
    parser.add_argument("--output-html", required=True, type=Path)
    args = parser.parse_args()

    hazop = load_json(args.hazop_json)
    topology = load_json(args.topology_json) if args.topology_json else {}
    design_root = args.design_root
    if design_root is None and hazop.get("metadata", {}).get("input_dir"):
        design_root = Path(hazop["metadata"]["input_dir"])
    if design_root is not None:
        design_root = design_root.expanduser().resolve()
    workbench = build_workbench(hazop, topology, design_root, max(0.12, min(args.preview_scale, 0.8)))
    html_text = render_html(workbench)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_text, encoding="utf-8", newline="\n")
    print(f"Wrote HAZOP workbench HTML to: {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
