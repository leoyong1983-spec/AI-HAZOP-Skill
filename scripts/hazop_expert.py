#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline HAZOP participating-expert review assistant."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
    ".log", ".ini", ".cfg", ".dat", ".srt"
}
DOC_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".xls", ".pdf"}
UNSUPPORTED_EXTENSIONS = {
    ".dwg", ".dxf", ".rvt", ".ifc", ".vsd", ".vsdx", ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".bmp", ".gif", ".7z", ".rar", ".zip", ".ppt", ".pptx", ".doc", ".xls"
}
IGNORE_DIR_NAMES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"
}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
ISSUE_PREFIX = {"critical": "C", "high": "H", "medium": "M", "low": "L"}

DOC_TYPE_PATTERNS: dict[str, list[str]] = {
    "design_basis": [r"design[_\- ]?basis", r"设计基础", r"设计依据", r"basis of design", r"适用标准", r"标准清单"],
    "pfd": [r"(?<![A-Za-z0-9])PFD(?![A-Za-z0-9])", r"process flow diagram", r"工艺流程图", r"流程图"],
    "pid": [r"(?<![A-Za-z0-9])P\s*&\s*ID(?![A-Za-z0-9])", r"(?<![A-Za-z0-9])P[\-_ ]?ID(?![A-Za-z0-9])", r"piping and instrumentation", r"管道仪表", r"管仪"],
    "equipment_list": [r"equipment[_\- ]?list", r"设备表", r"设备清单", r"equipment datasheet", r"设备数据表"],
    "line_list": [r"line[_\- ]?list", r"管线表", r"管道表", r"line designation", r"管线号"],
    "instrument_index": [r"instrument[_\- ]?index", r"仪表索引", r"仪表清单", r"alarm list", r"报警清单", r"trip list", r"联锁清单"],
    "cause_effect": [r"cause[_\- ]?(?:&|and|\||,)?[_\- ]?effect", r"(?<![A-Za-z0-9])C\s*&\s*E(?![A-Za-z0-9])", r"因果", r"ESD逻辑", r"联锁矩阵"],
    "control_philosophy": [r"control[_\- ]?philosophy", r"控制哲学", r"操作说明", r"operation manual", r"操作手册", r"开车", r"停车"],
    "relief_flare": [r"relief", r"泄压", r"安全阀", r"\bPSV\b", r"\bPRV\b", r"flare", r"火炬", r"vent", r"放空"],
    "hazardous_area": [r"hazardous[_\- ]?area", r"危险区域", r"防爆", r"explosion proof", r"area classification"],
    "layout": [r"plot[_\- ]?plan", r"layout", r"总图", r"设备布置", r"平面布置", r"围堰", r"集液池"],
    "sil_sis": [r"\bSIL\b", r"\bSIS\b", r"安全仪表", r"LOPA", r"保护层"],
    "fire_gas": [r"fire and gas", r"\bFGS\b", r"可燃气", r"火焰探测", r"消防", r"firewater", r"火灾"],
    "material_corrosion": [r"material", r"材料", r"腐蚀", r"corrosion", r"低温材料", r"保冷", r"insulation"],
    "datasheet": [r"datasheet", r"data sheet", r"数据表", r"规格书", r"specification"],
    "incident_history": [r"incident", r"near[_\- ]?miss", r"lesson[_\- ]?learned", r"accident", r"事故", r"未遂", r"险情", r"经验反馈", r"事故教训"],
    "moc_pssr": [r"\bMOC\b", r"management[_\- ]?of[_\- ]?change", r"\bPSSR\b", r"pre[-_ ]?startup", r"变更管理", r"开车前安全审查", r"投产前安全审查"],
    "operating_procedure": [r"operating[_\- ]?procedure", r"\bSOP\b", r"operation[_\- ]?manual", r"操作规程", r"运行规程", r"启动", r"停车", r"应急停车"],
    "maintenance_procedure": [r"maintenance[_\- ]?procedure", r"inspection[_\- ]?test", r"mechanical[_\- ]?integrity", r"检维修", r"维护规程", r"完整性", r"试验记录"],
    "emergency_response": [r"emergency[_\- ]?response", r"emergency[_\- ]?plan", r"fire[_\- ]?drill", r"应急预案", r"消防演练", r"火灾应急"],
    "natural_hazard": [r"natural[_\- ]?hazard", r"flood", r"storm[_\- ]?surge", r"typhoon", r"earthquake", r"lightning", r"自然灾害", r"洪水", r"台风", r"风暴潮", r"地震", r"雷电"],
    "facility_siting": [r"facility[_\- ]?siting", r"stationary[_\- ]?source[_\- ]?siting", r"occupied[_\- ]?building", r"public[_\- ]?receptor", r"building[_\- ]?risk", r"设施选址", r"人员密集", r"公众敏感点", r"建筑物抗爆"],
    "utility_system": [r"utility", r"power[_\- ]?failure", r"standby[_\- ]?power", r"backup[_\- ]?power", r"instrument[_\- ]?air", r"nitrogen", r"cooling[_\- ]?water", r"公用工程", r"备用电源", r"仪表风", r"氮气", r"冷却水"],
    "ship_shore": [r"ship[_\- ]?shore", r"\bSSL\b", r"marine[_\- ]?loading[_\- ]?arm", r"emergency[_\- ]?release", r"\bERS\b", r"船岸", r"装卸臂", r"紧急释放"],
    "cyber_security": [r"cyber", r"network[_\- ]?security", r"\bDCS\b", r"\bPLC\b", r"remote[_\- ]?access", r"网络安全", r"远程访问", r"控制系统安全"],
    "action_tracking": [r"recommendation", r"action[_\- ]?item", r"tracking", r"close[_\- ]?out", r"整改", r"建议项", r"行动项", r"关闭"],
    "hazop_record": [r"HAZOP.*记录", r"HAZOP[_\- ]?worksheet", r"HAZOP[_\- ]?record", r"分析记录表", r"偏差", r"引导词", r"设计意图", r"固有风险", r"残余风险"],
    "high_risk_summary": [r"高风险", r"复杂剧情", r"high[_\- ]?risk", r"complex[_\- ]?scenario"],
    "review_comments": [r"审查意见", r"修改意见", r"review[_\- ]?comment", r"comment[_\- ]?response", r"问题描述", r"修改建议"],
    "sil_report": [r"SIL定级", r"SIL评估", r"安全完整性等级", r"LOPA", r"SIF", r"exSILentia"],
    "sil_record": [r"SIL定级记录", r"保护层分析表", r"Layer of Protection Analysis", r"Hazard Scenario ID", r"RequiredSIL", r"RRF"],
    "interface_boundary": [r"界区", r"界面", r"接口", r"boundary", r"interface", r"battery[_\- ]?limit"],
    "node_diagram": [r"节点图", r"node[_\- ]?diagram"],
    "sds_msds": [r"\bMSDS\b", r"\bSDS\b", r"安全数据表", r"化学品安全技术说明书"],
}

SIGNAL_PATTERNS: dict[str, list[str]] = {
    "lng": [r"\bLNG\b", r"液化天然气", r"接收站", r"卸船", r"BOG", r"boil[- ]?off", r"气化器", r"储罐"],
    "cryogenic": [r"cryogenic", r"低温", r"保冷", r"cold box", r"embrittlement", r"脆裂"],
    "brownfield": [r"扩建", r"改造", r"existing", r"brownfield", r"tie[- ]?in", r"接口", r"切改", r"SIMOPS"],
    "flammable": [r"flammable", r"可燃", r"天然气", r"methane", r"甲烷", r"hydrocarbon", r"烃"],
    "marine_transfer": [r"ship[_\- ]?shore", r"\bSSL\b", r"loading arm", r"marine[_\- ]?loading", r"jetty", r"船岸", r"装卸臂", r"码头"],
    "natural_hazard": [r"natural[_\- ]?hazard", r"flood", r"storm[_\- ]?surge", r"typhoon", r"earthquake", r"lightning", r"自然灾害", r"洪水", r"台风", r"风暴潮", r"地震", r"雷电"],
    "digital_control": [r"\bDCS\b", r"\bSIS\b", r"\bPLC\b", r"cyber", r"remote[_\- ]?access", r"网络安全", r"控制系统", r"远程访问"],
}

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


@dataclasses.dataclass
class DocumentRecord:
    path: str
    rel_path: str
    extension: str
    size_bytes: int
    sha256: str
    method: str
    text: str
    doc_types: list[str]
    tags: list[str]
    warnings: list[str]


@dataclasses.dataclass
class Evidence:
    rel_path: str
    keyword: str
    excerpt: str
    tags: list[str]


@dataclasses.dataclass
class Issue:
    issue_id: str
    priority: str
    confidence: str
    topic: str
    node: str
    guidewords: list[str]
    concern: str
    expert_questions: list[str]
    requested_evidence: list[str]
    evidence: list[Evidence]
    source_rule: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review a process design package and draft HAZOP expert questions.")
    parser.add_argument("--input", "-i", required=True, help="Folder containing design files.")
    parser.add_argument("--output", "-o", default=None, help="Folder for review outputs. Defaults to ./hazop_review_output.")
    parser.add_argument("--project-name", default="", help="Project name shown in the report.")
    parser.add_argument("--rule-catalog", default="", help="Optional JSON rule catalog path.")
    parser.add_argument("--max-file-mb", type=float, default=40.0, help="Skip files larger than this size.")
    parser.add_argument("--pdf-page-limit", type=int, default=120, help="Maximum PDF pages to extract per file.")
    parser.add_argument("--max-excerpts-per-rule", type=int, default=4, help="Maximum evidence excerpts per triggered rule.")
    parser.add_argument("--include-unsupported", action="store_true", help="List unsupported binary files in the index.")
    args = parser.parse_args(argv)

    input_dir = Path(args.input).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input folder does not exist or is not a directory: {input_dir}", file=sys.stderr)
        return 2

    output_dir = Path(args.output).expanduser().resolve() if args.output else (Path.cwd() / "hazop_review_output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = Path(args.rule_catalog).expanduser().resolve() if args.rule_catalog else default_catalog_path()
    catalog = load_catalog(catalog_path)

    records, unsupported = collect_documents(
        input_dir=input_dir,
        output_dir=output_dir,
        max_file_bytes=int(args.max_file_mb * 1024 * 1024),
        pdf_page_limit=args.pdf_page_limit,
        include_unsupported=args.include_unsupported,
    )
    findings = analyze(records, unsupported, catalog, args.max_excerpts_per_rule)
    package = build_package(args.project_name, input_dir, output_dir, records, unsupported, findings, catalog_path, catalog)
    write_outputs(output_dir, package)

    print(f"Wrote HAZOP expert review package to: {output_dir}")
    print(f"Issues: {len(package['issues'])}; documents read: {len(records)}; unsupported/skipped: {len(unsupported)}")
    print(f"Open: {output_dir / 'hazop_expert_opinions.md'}")
    return 0


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "rule_catalog.json"


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise SystemExit(f"Failed to load rule catalog {path}: {exc}") from exc


def collect_documents(
    input_dir: Path,
    output_dir: Path,
    max_file_bytes: int,
    pdf_page_limit: int,
    include_unsupported: bool,
) -> tuple[list[DocumentRecord], list[dict[str, Any]]]:
    records: list[DocumentRecord] = []
    unsupported: list[dict[str, Any]] = []

    for path in sorted(input_dir.rglob("*")):
        if path.is_dir():
            continue
        if should_ignore(path, input_dir, output_dir):
            continue
        rel = str(path.relative_to(input_dir))
        ext = path.suffix.lower()
        size = path.stat().st_size
        if size > max_file_bytes:
            unsupported.append({"rel_path": rel, "extension": ext, "reason": f"skipped_size_gt_{max_file_bytes}"})
            continue
        if ext not in TEXT_EXTENSIONS and ext not in DOC_EXTENSIONS:
            if include_unsupported or ext in UNSUPPORTED_EXTENSIONS:
                unsupported.append({"rel_path": rel, "extension": ext, "reason": "unsupported_or_binary"})
            continue
        record = extract_document(path, input_dir, pdf_page_limit)
        records.append(record)

    return records, unsupported


def should_ignore(path: Path, input_dir: Path, output_dir: Path) -> bool:
    parts = set(path.relative_to(input_dir).parts[:-1])
    if parts.intersection(IGNORE_DIR_NAMES):
        return True
    try:
        path.resolve().relative_to(output_dir)
        return True
    except ValueError:
        return False


def extract_document(path: Path, input_dir: Path, pdf_page_limit: int) -> DocumentRecord:
    ext = path.suffix.lower()
    warnings: list[str] = []
    method = "text"
    try:
        if ext in TEXT_EXTENSIONS:
            text, method = read_textish(path)
        elif ext == ".docx":
            text, method = read_docx(path)
        elif ext in {".xlsx", ".xlsm"}:
            text, method = read_xlsx(path)
        elif ext == ".xls":
            text, method = read_xls(path)
        elif ext == ".pdf":
            text, method, pdf_warnings = read_pdf(path, pdf_page_limit)
            warnings.extend(pdf_warnings)
        else:
            text, method = "", "unsupported"
    except Exception as exc:
        text = ""
        method = "failed"
        warnings.append(f"extract_failed: {type(exc).__name__}: {exc}")

    if not text.strip():
        warnings.append("no_extractable_text")

    rel = str(path.relative_to(input_dir))
    combined = f"{rel}\n{text[:30000]}"
    doc_types = sorted(classify_doc_types(combined))
    tags = sorted(set(normalize_tag(t) for t in TAG_RE.findall(text)))[:200]
    return DocumentRecord(
        path=str(path),
        rel_path=rel,
        extension=ext,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        method=method,
        text=normalize_text(text),
        doc_types=doc_types,
        tags=tags,
        warnings=warnings,
    )


def read_textish(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "cp936", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
        enc = "utf-8-replace"
    if path.suffix.lower() in {".html", ".htm"}:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(text)
        return text, f"html:{enc}"
    if path.suffix.lower() == ".csv":
        return csv_to_text(path, enc), f"csv:{enc}"
    if path.suffix.lower() == ".tsv":
        return csv_to_text(path, enc, delimiter="\t"), f"tsv:{enc}"
    return text, f"text:{enc}"


def csv_to_text(path: Path, encoding: str, delimiter: str = ",") -> str:
    rows: list[str] = []
    with path.open("r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for i, row in enumerate(reader):
            if i >= 5000:
                rows.append("[truncated after 5000 rows]")
                break
            rows.append(" | ".join(str(c) for c in row))
    return "\n".join(rows)


def read_docx(path: Path) -> tuple[str, str]:
    try:
        import docx  # type: ignore

        doc = docx.Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts), "docx:python-docx"
    except Exception:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        texts = [node.text or "" for node in root.iter() if node.tag.endswith("}t")]
        return "\n".join(texts), "docx:xml"


def read_xlsx(path: Path) -> tuple[str, str]:
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        lines: list[str] = []
        cell_count = 0
        for ws in wb.worksheets:
            lines.append(f"[SHEET] {ws.title}")
            for row in ws.iter_rows(values_only=True):
                values = [str(v) for v in row if v is not None and str(v).strip()]
                if values:
                    lines.append(" | ".join(values))
                cell_count += len(row)
                if cell_count > 120000:
                    lines.append("[truncated after 120000 cells]")
                    return "\n".join(lines), "xlsx:openpyxl:truncated"
        return "\n".join(lines), "xlsx:openpyxl"
    except Exception:
        return read_xlsx_zip_fallback(path), "xlsx:zip-fallback"


def read_xls(path: Path) -> tuple[str, str]:
    try:
        import xlrd  # type: ignore
    except Exception as exc:
        return "", f"xls:xlrd-missing:{type(exc).__name__}"

    book = xlrd.open_workbook(str(path), on_demand=True)
    lines: list[str] = []
    cell_count = 0
    for sheet_name in book.sheet_names():
        sh = book.sheet_by_name(sheet_name)
        lines.append(f"[SHEET] {sheet_name}")
        for ri in range(sh.nrows):
            values = []
            for ci in range(sh.ncols):
                value = sh.cell_value(ri, ci)
                if value not in ("", None):
                    values.append(str(value))
            if values:
                lines.append(" | ".join(values))
            cell_count += sh.ncols
            if cell_count > 120000:
                lines.append("[truncated after 120000 cells]")
                return "\n".join(lines), "xls:xlrd:truncated"
    return "\n".join(lines), "xls:xlrd"


def read_xlsx_zip_fallback(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".xml")]
        for name in names:
            if "sharedStrings" not in name and "worksheets" not in name:
                continue
            raw = zf.read(name)
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            for node in root.iter():
                if node.text and node.text.strip():
                    texts.append(node.text.strip())
    return "\n".join(texts[:50000])


def read_pdf(path: Path, page_limit: int) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    reader = None
    method = ""
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        method = "pdf:pypdf"
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            method = "pdf:PyPDF2"
        except Exception as exc:
            return "", "pdf:failed", [f"pdf_extract_failed: {type(exc).__name__}: {exc}"]

    pages = list(reader.pages)
    if page_limit > 0 and len(pages) > page_limit:
        warnings.append(f"pdf_truncated_pages:{page_limit}_of_{len(pages)}")
        pages = pages[:page_limit]

    parts: list[str] = []
    for i, page in enumerate(pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception as exc:
            warnings.append(f"page_{i}_extract_failed:{type(exc).__name__}")
            txt = ""
        if txt.strip():
            parts.append(f"[PAGE {i}]\n{txt}")
    return "\n\n".join(parts), method, warnings


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def classify_doc_types(combined: str) -> set[str]:
    found: set[str] = set()
    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        if any(re.search(p, combined, flags=re.IGNORECASE) for p in patterns):
            found.add(doc_type)
    return found


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_tag(tag: str) -> str:
    return re.sub(r"\s+", "-", tag.upper())


def analyze(
    records: list[DocumentRecord],
    unsupported: list[dict[str, Any]],
    catalog: dict[str, Any],
    max_excerpts_per_rule: int,
) -> list[Issue]:
    issues: list[Issue] = []
    doc_counts = doc_type_counts(records)
    signals = detect_signals(records)

    for required in catalog.get("required_document_types", []):
        dtype = required["type"]
        if doc_counts.get(dtype, 0) == 0:
            issues.append(Issue(
                issue_id="",
                priority=required.get("priority", "medium"),
                confidence="high",
                topic=f"资料缺口：{required.get('label', dtype)}",
                node="项目/会议准备",
                guidewords=["Information gap"],
                concern=required.get("why", ""),
                expert_questions=[required.get("question", "请补充该类文件并说明对HAZOP节点的影响。")],
                requested_evidence=[required.get("label", dtype)],
                evidence=[],
                source_rule=f"required_document_type:{dtype}",
            ))

    if not records:
        issues.append(Issue(
            issue_id="",
            priority="critical",
            confidence="high",
            topic="无法读取设计资料",
            node="项目/会议准备",
            guidewords=["Information gap"],
            concern="输入目录没有可读取的文本、Word、Excel或PDF内容，无法形成有证据的专家问题。",
            expert_questions=["请提供可复制文本的PDF、Word、Excel、P&ID导出文本、OCR结果或图纸索引；哪些关键图纸目前只有扫描件？"],
            requested_evidence=["可读取的设计资料包", "图纸目录", "OCR文本"],
            evidence=[],
            source_rule="system:no_records",
        ))

    unreadable = [r for r in records if "no_extractable_text" in r.warnings]
    if unreadable:
        sample = [Evidence(r.rel_path, "no_extractable_text", "文件可见但未能提取文本，可能是扫描件或二进制图纸。", []) for r in unreadable[:8]]
        issues.append(Issue(
            issue_id="",
            priority="medium",
            confidence="high",
            topic="部分文件不可文本检索",
            node="资料质量",
            guidewords=["Information gap"],
            concern="扫描件、图片型PDF或原生CAD文件未OCR时，工具无法检查其中的阀门、仪表、节点和注释。",
            expert_questions=["请确认这些文件是否为最新有效设计文件；如是，请提供OCR文本、可搜索PDF或图纸数据导出。"],
            requested_evidence=["OCR结果", "可搜索PDF", "图纸清单"],
            evidence=sample,
            source_rule="system:unreadable_files",
        ))

    if unsupported:
        sample = [Evidence(u["rel_path"], u.get("extension", ""), f"未解析：{u.get('reason', '')}", []) for u in unsupported[:10]]
        issues.append(Issue(
            issue_id="",
            priority="low",
            confidence="high",
            topic="存在未解析的二进制或大文件",
            node="资料质量",
            guidewords=["Information gap"],
            concern="CAD、图片、压缩包或超大文件可能包含HAZOP关键信息，但本次离线文本引擎未解析。",
            expert_questions=["这些未解析文件中是否包含P&ID、总图、危险区域、防火、供应商数据或C&E矩阵？请提供对应可搜索版本。"],
            requested_evidence=["文件目录说明", "可搜索导出版"],
            evidence=sample,
            source_rule="system:unsupported_files",
        ))

    for rule in catalog.get("rules", []):
        if not rule_applies(rule, records, signals):
            continue
        evidence = find_evidence(records, rule.get("any_keywords", []), max_excerpts_per_rule)
        confidence = "medium" if evidence else "low"
        if evidence and len(evidence) >= min(2, max_excerpts_per_rule):
            confidence = "high"
        issues.append(Issue(
            issue_id="",
            priority=rule.get("priority", "medium"),
            confidence=confidence,
            topic=rule.get("topic", rule.get("id", "HAZOP问题")),
            node=infer_node(rule, evidence),
            guidewords=rule.get("guidewords", []),
            concern=rule.get("concern", ""),
            expert_questions=rule.get("questions", []),
            requested_evidence=rule.get("requested_evidence", []),
            evidence=evidence,
            source_rule=rule.get("id", "rule"),
        ))

    issues = sorted(issues, key=lambda x: (PRIORITY_ORDER.get(x.priority, 9), x.topic, x.source_rule))
    for index, issue in enumerate(issues, start=1):
        issue.issue_id = f"HAZOP-{ISSUE_PREFIX.get(issue.priority, 'X')}{index:03d}"
    return issues


def doc_type_counts(records: list[DocumentRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        for dtype in r.doc_types:
            counts[dtype] = counts.get(dtype, 0) + 1
    return counts


def detect_signals(records: list[DocumentRecord]) -> set[str]:
    text = "\n".join(f"{r.rel_path}\n{r.text[:100000]}" for r in records)
    signals: set[str] = set()
    for signal, patterns in SIGNAL_PATTERNS.items():
        if any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
            signals.add(signal)
    return signals


def rule_applies(rule: dict[str, Any], records: list[DocumentRecord], signals: set[str]) -> bool:
    required_signals = set(rule.get("signals", []))
    if required_signals and not required_signals.issubset(signals):
        return False
    doc_types = set(rule.get("doc_types", []))
    if doc_types:
        found_types = set()
        for r in records:
            found_types.update(r.doc_types)
        if not doc_types.intersection(found_types):
            return False
    keywords = rule.get("any_keywords", [])
    if not keywords:
        return True
    haystack = "\n".join(f"{r.rel_path}\n{r.text[:200000]}" for r in records)
    return any(re.search(re.escape(k), haystack, flags=re.IGNORECASE) for k in keywords)


def find_evidence(records: list[DocumentRecord], keywords: Iterable[str], limit: int) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[tuple[str, str]] = set()
    for keyword in keywords:
        if len(evidence) >= limit:
            break
        pattern = re.compile(re.escape(keyword), flags=re.IGNORECASE)
        for record in records:
            if len(evidence) >= limit:
                break
            search_space = f"{record.rel_path}\n{record.text}"
            match = pattern.search(search_space)
            if not match:
                continue
            key = (record.rel_path, keyword.lower())
            if key in seen:
                continue
            seen.add(key)
            excerpt = make_excerpt(search_space, match.start(), match.end())
            evidence.append(Evidence(record.rel_path, keyword, excerpt, sorted(set(normalize_tag(t) for t in TAG_RE.findall(excerpt)))[:10]))
    return evidence


def make_excerpt(text: str, start: int, end: int, width: int = 460) -> str:
    left = max(0, start - width // 2)
    right = min(len(text), end + width // 2)
    excerpt = text[left:right]
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if left > 0:
        excerpt = "..." + excerpt
    if right < len(text):
        excerpt += "..."
    return excerpt


def infer_node(rule: dict[str, Any], evidence: list[Evidence]) -> str:
    topic = rule.get("topic", "")
    if evidence:
        tags = []
        for ev in evidence:
            tags.extend(ev.tags)
        if tags:
            return "相关设备/仪表：" + ", ".join(sorted(set(tags))[:8])
    if "LNG" in topic or "低温" in topic:
        return "LNG/低温系统"
    if "BOG" in topic:
        return "BOG系统"
    if "储罐" in topic:
        return "储罐系统"
    if "气化" in topic:
        return "气化/外输系统"
    return "项目/系统层面"


def build_package(
    project_name: str,
    input_dir: Path,
    output_dir: Path,
    records: list[DocumentRecord],
    unsupported: list[dict[str, Any]],
    issues: list[Issue],
    catalog_path: Path,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    counts = doc_type_counts(records)
    signals = sorted(detect_signals(records))
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "metadata": {
            "project_name": project_name or input_dir.name,
            "generated_at": now,
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "rule_catalog": str(catalog_path),
            "role": "HAZOP participating expert, not chair",
            "method_note": "Offline evidence-based screening. Questions require human expert review before meeting use.",
        },
        "signals": signals,
        "practice_sources": catalog.get("practice_sources", []),
        "document_type_counts": counts,
        "documents": [record_to_index(r) for r in records],
        "unsupported_or_skipped": unsupported,
        "issues": [issue_to_dict(i) for i in issues],
    }


def record_to_index(record: DocumentRecord) -> dict[str, Any]:
    return {
        "rel_path": record.rel_path,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "method": record.method,
        "doc_types": record.doc_types,
        "tag_count": len(record.tags),
        "tags_sample": record.tags[:40],
        "text_chars": len(record.text),
        "warnings": record.warnings,
    }


def issue_to_dict(issue: Issue) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "priority": issue.priority,
        "confidence": issue.confidence,
        "topic": issue.topic,
        "node": issue.node,
        "guidewords": issue.guidewords,
        "concern": issue.concern,
        "expert_questions": issue.expert_questions,
        "requested_evidence": issue.requested_evidence,
        "evidence": [dataclasses.asdict(e) for e in issue.evidence],
        "source_rule": issue.source_rule,
    }


def write_outputs(output_dir: Path, package: dict[str, Any]) -> None:
    (output_dir / "hazop_expert_opinions.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "extracted_index.json").write_text(
        json.dumps({
            "metadata": package["metadata"],
            "signals": package["signals"],
            "practice_sources": package.get("practice_sources", []),
            "document_type_counts": package["document_type_counts"],
            "documents": package["documents"],
            "unsupported_or_skipped": package["unsupported_or_skipped"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "hazop_expert_opinions.md").write_text(render_markdown(package), encoding="utf-8")
    write_csv(output_dir / "hazop_expert_questions.csv", package["issues"])
    (output_dir / "review_prompt.md").write_text(render_review_prompt(package), encoding="utf-8")
    (output_dir / "run_summary.json").write_text(
        json.dumps({
            "generated_at": package["metadata"]["generated_at"],
            "project_name": package["metadata"]["project_name"],
            "issue_count": len(package["issues"]),
            "document_count": len(package["documents"]),
            "unsupported_or_skipped_count": len(package["unsupported_or_skipped"]),
            "outputs": [
                "hazop_expert_opinions.md",
                "hazop_expert_opinions.json",
                "hazop_expert_questions.csv",
                "extracted_index.json",
                "review_prompt.md",
            ],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def render_markdown(package: dict[str, Any]) -> str:
    meta = package["metadata"]
    issues = package["issues"]
    priority_counts: dict[str, int] = {}
    for issue in issues:
        priority_counts[issue["priority"]] = priority_counts.get(issue["priority"], 0) + 1

    lines: list[str] = []
    lines.append(f"# HAZOP专家意见筛查报告 - {meta['project_name']}")
    lines.append("")
    lines.append(f"- 生成时间：{meta['generated_at']}")
    lines.append(f"- 输入目录：`{meta['input_dir']}`")
    lines.append(f"- 工具角色：HAZOP参会专家问题筛查，不是主席结论或正式会议纪要")
    lines.append(f"- 识别项数：{len(issues)}")
    lines.append(f"- 优先级统计：{', '.join(f'{k}={v}' for k, v in sorted(priority_counts.items(), key=lambda x: PRIORITY_ORDER.get(x[0], 9))) or '无'}")
    lines.append("")
    lines.append("## 使用边界")
    lines.append("")
    lines.append("本报告用于会前准备和专家发问。它依据输入文件的可提取文本和规则库生成问题，不代表设计确认、风险评级、主席行动项关闭或正式HAZOP worksheet。扫描图、CAD原图、压缩包和无法提取文本的PDF需要另行OCR或人工核查。")
    lines.append("")
    if package.get("practice_sources"):
        lines.append("## 借鉴来源")
        lines.append("")
        for source in package["practice_sources"]:
            label = source.get("label", "")
            url = source.get("url", "")
            borrowed = source.get("borrowed", "")
            if url:
                lines.append(f"- {label}: {url}；借鉴点：{borrowed}")
            else:
                lines.append(f"- {label}；借鉴点：{borrowed}")
        lines.append("")
    lines.append("## 资料概况")
    lines.append("")
    lines.append(f"- 已读取文件：{len(package['documents'])}")
    lines.append(f"- 未解析/跳过文件：{len(package['unsupported_or_skipped'])}")
    lines.append(f"- 项目信号：{', '.join(package['signals']) or '未识别明显行业信号'}")
    lines.append("")
    lines.append("| 文档类型 | 数量 |")
    lines.append("| --- | ---: |")
    for key, value in sorted(package["document_type_counts"].items()):
        lines.append(f"| {escape_pipe(key)} | {value} |")
    if not package["document_type_counts"]:
        lines.append("| 未识别 | 0 |")
    lines.append("")
    lines.append("## 优先问题总表")
    lines.append("")
    lines.append("| ID | 优先级 | 置信度 | 主题 | 节点/对象 | 首要专家问题 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for issue in issues:
        first_q = issue["expert_questions"][0] if issue["expert_questions"] else ""
        lines.append(
            f"| {issue['issue_id']} | {issue['priority']} | {issue['confidence']} | "
            f"{escape_pipe(issue['topic'])} | {escape_pipe(issue['node'])} | {escape_pipe(first_q)} |"
        )
    lines.append("")
    lines.append("## 详细专家意见")
    lines.append("")
    for issue in issues:
        lines.append(f"### {issue['issue_id']} {issue['topic']}")
        lines.append("")
        lines.append(f"- 优先级：{issue['priority']}")
        lines.append(f"- 置信度：{issue['confidence']}（基于输入资料命中程度，不等同风险等级）")
        lines.append(f"- 节点/对象：{issue['node']}")
        lines.append(f"- 导向词：{', '.join(issue['guidewords']) or '未指定'}")
        lines.append(f"- 触发规则：`{issue['source_rule']}`")
        lines.append("")
        if issue["concern"]:
            lines.append("关注点：")
            lines.append("")
            lines.append(issue["concern"])
            lines.append("")
        if issue["expert_questions"]:
            lines.append("建议在会上提出：")
            lines.append("")
            for i, q in enumerate(issue["expert_questions"], start=1):
                lines.append(f"{i}. {q}")
            lines.append("")
        if issue["requested_evidence"]:
            lines.append("建议要求补充/定位的证据：")
            lines.append("")
            for item in issue["requested_evidence"]:
                lines.append(f"- {item}")
            lines.append("")
        if issue["evidence"]:
            lines.append("输入资料证据摘录：")
            lines.append("")
            for ev in issue["evidence"]:
                tags = f"；tags: {', '.join(ev['tags'])}" if ev.get("tags") else ""
                lines.append(f"- `{ev['rel_path']}`；关键词：`{ev['keyword']}`{tags}")
                lines.append(f"  - {ev['excerpt']}")
            lines.append("")
        else:
            lines.append("输入资料证据摘录：无直接摘录；该项主要由资料缺口或项目级规则触发。")
            lines.append("")
    lines.append("## 文件索引摘录")
    lines.append("")
    lines.append("| 文件 | 方法 | 类型 | 字符数 | 警告 |")
    lines.append("| --- | --- | --- | ---: | --- |")
    for doc in package["documents"][:80]:
        lines.append(
            f"| `{escape_pipe(doc['rel_path'])}` | {escape_pipe(doc['method'])} | "
            f"{escape_pipe(', '.join(doc['doc_types']))} | {doc['text_chars']} | {escape_pipe(', '.join(doc['warnings']))} |"
        )
    if len(package["documents"]) > 80:
        lines.append(f"| ... | ... | ... | ... | 另有 {len(package['documents']) - 80} 个文件见 JSON 索引 |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, issues: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_id", "priority", "confidence", "topic", "node", "guidewords",
                "concern", "expert_questions", "requested_evidence", "evidence_files", "source_rule"
            ],
        )
        writer.writeheader()
        for issue in issues:
            writer.writerow({
                "issue_id": issue["issue_id"],
                "priority": issue["priority"],
                "confidence": issue["confidence"],
                "topic": issue["topic"],
                "node": issue["node"],
                "guidewords": "; ".join(issue["guidewords"]),
                "concern": issue["concern"],
                "expert_questions": "\n".join(issue["expert_questions"]),
                "requested_evidence": "; ".join(issue["requested_evidence"]),
                "evidence_files": "; ".join(sorted({ev["rel_path"] for ev in issue["evidence"]})),
                "source_rule": issue["source_rule"],
            })


def render_review_prompt(package: dict[str, Any]) -> str:
    meta = package["metadata"]
    top = package["issues"][:20]
    lines = [
        f"# 复核提示包 - {meta['project_name']}",
        "",
        "你是HAZOP参会专家，不是主席。请基于 `hazop_expert_opinions.json` 和源设计文件复核以下问题：",
        "",
        "1. 删除没有证据或不适用于本项目边界的问题。",
        "2. 合并重复问题，并保留最具体、最可执行的发问。",
        "3. 对每个保留问题补充需要哪个专业/哪份文件回答。",
        "4. 不要给出主席结论，不要关闭行动项。",
        "",
        "## 优先复核问题",
        "",
    ]
    for issue in top:
        q = issue["expert_questions"][0] if issue["expert_questions"] else ""
        lines.append(f"- {issue['issue_id']} [{issue['priority']}] {issue['topic']}: {q}")
    return "\n".join(lines) + "\n"


def escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
