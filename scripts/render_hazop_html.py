"""Render an offline HTML dashboard from AI-HAZOP JSON output."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_LABEL = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_excerpt(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.strip()


def compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": issue.get("issue_id", ""),
        "priority": issue.get("priority", ""),
        "priorityLabel": PRIORITY_LABEL.get(issue.get("priority", ""), issue.get("priority", "")),
        "confidence": issue.get("confidence", ""),
        "topic": issue.get("topic", ""),
        "node": issue.get("node", ""),
        "guidewords": issue.get("guidewords", []),
        "concern": issue.get("concern", ""),
        "questions": issue.get("expert_questions", []),
        "requestedEvidence": issue.get("requested_evidence", []),
        "evidence": issue.get("evidence", []),
        "sourceRule": issue.get("source_rule", ""),
        "searchText": " ".join(
            [
                str(issue.get("issue_id", "")),
                str(issue.get("priority", "")),
                str(issue.get("topic", "")),
                str(issue.get("node", "")),
                str(issue.get("concern", "")),
                " ".join(str(x) for x in issue.get("guidewords", [])),
                " ".join(str(x) for x in issue.get("expert_questions", [])),
                " ".join(str(x) for x in issue.get("requested_evidence", [])),
                " ".join(str(x.get("rel_path", "")) for x in issue.get("evidence", []) if isinstance(x, dict)),
                " ".join(str(x.get("keyword", "")) for x in issue.get("evidence", []) if isinstance(x, dict)),
            ]
        ).lower(),
    }


def compact_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": finding.get("finding_id", ""),
        "priority": finding.get("priority", ""),
        "priorityLabel": PRIORITY_LABEL.get(finding.get("priority", ""), finding.get("priority", "")),
        "confidence": finding.get("confidence", ""),
        "parameter": finding.get("parameter", ""),
        "guidewords": finding.get("guidewords", []),
        "analysisObject": finding.get("analysis_object", ""),
        "problem": finding.get("problem", ""),
        "possibleCauses": finding.get("possible_causes", []),
        "possibleConsequences": finding.get("possible_consequences", []),
        "safeguardsToVerify": finding.get("existing_safeguards_to_verify", []),
        "expertActions": finding.get("expert_actions", []),
        "evidence": finding.get("evidence", []),
        "relatedDocuments": finding.get("related_documents", []),
        "sourceRule": finding.get("source_rule", ""),
        "searchText": " ".join(
            [
                str(finding.get("finding_id", "")),
                str(finding.get("priority", "")),
                str(finding.get("parameter", "")),
                str(finding.get("analysis_object", "")),
                str(finding.get("problem", "")),
                " ".join(str(x) for x in finding.get("guidewords", [])),
                " ".join(str(x) for x in finding.get("possible_causes", [])),
                " ".join(str(x) for x in finding.get("possible_consequences", [])),
                " ".join(str(x) for x in finding.get("existing_safeguards_to_verify", [])),
                " ".join(str(x) for x in finding.get("expert_actions", [])),
                " ".join(str(x) for x in finding.get("related_documents", [])),
                " ".join(str(x.get("keyword", "")) for x in finding.get("evidence", []) if isinstance(x, dict)),
                " ".join(str(x.get("excerpt", "")) for x in finding.get("evidence", []) if isinstance(x, dict)),
            ]
        ).lower(),
    }


def compact_drawing_review(review: dict[str, Any]) -> dict[str, Any]:
    findings = [compact_finding(item) for item in review.get("findings", [])]
    search_text = " ".join(
        [
            str(review.get("drawing_id", "")),
            str(review.get("drawing_no", "")),
            str(review.get("rel_path", "")),
            str(review.get("title", "")),
            str(review.get("node_hint", "")),
            str(review.get("design_intent_hint", "")),
            " ".join(str(x) for x in review.get("review_focus", [])),
            " ".join(item["searchText"] for item in findings),
        ]
    ).lower()
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
        "searchText": search_text,
    }


def render_dashboard(data: dict[str, Any], red_team_notes: str) -> str:
    issues = sorted(
        [compact_issue(issue) for issue in data.get("issues", [])],
        key=lambda item: (PRIORITY_ORDER.get(item["priority"], 99), item["id"]),
    )
    drawing_reviews = [compact_drawing_review(review) for review in data.get("drawing_reviews", [])]
    finding_counts = Counter(
        finding["priority"]
        for review in drawing_reviews
        for finding in review["findings"]
    )
    counts = finding_counts or Counter(issue["priority"] for issue in issues)
    metadata = data.get("metadata", {})
    doc_type_counts = data.get("document_type_counts", {})
    signals = data.get("signals", [])
    docs = data.get("documents", [])
    low_text_docs = [doc for doc in docs if int(doc.get("text_chars") or 0) < 600]

    js_data = json.dumps(
        {
            "issues": issues,
            "drawingReviews": drawing_reviews,
            "counts": counts,
        },
        ensure_ascii=False,
    )
    script_json = (
        js_data.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("</", "<\\/")
    )

    stat_cards = "\n".join(
        f"""
        <div class="stat {priority}">
          <div class="stat-value">{counts.get(priority, 0)}</div>
          <div class="stat-label">{PRIORITY_LABEL[priority]}</div>
        </div>
        """
        for priority in ["critical", "high", "medium", "low"]
    )

    doc_type_items = "\n".join(
        f'<span class="chip">{esc(name)} <b>{esc(count)}</b></span>'
        for name, count in sorted(doc_type_counts.items(), key=lambda item: (-int(item[1]), item[0]))
    )
    signal_items = "\n".join(f'<span class="chip signal">{esc(signal)}</span>' for signal in signals)
    low_doc_items = "\n".join(
        f'<li><span>{esc(doc.get("rel_path"))}</span><b>{esc(doc.get("text_chars"))} 字符</b></li>'
        for doc in low_text_docs[:20]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI-HAZOP 逐图纸预审仪表板</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #18202a;
      --muted: #667085;
      --border: #d9dee7;
      --critical: #b42318;
      --critical-bg: #fff1f0;
      --high: #b54708;
      --high-bg: #fff6e6;
      --medium: #175cd3;
      --medium-bg: #edf4ff;
      --low: #475467;
      --low-bg: #f2f4f7;
      --accent: #006d77;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
      line-height: 1.5;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--border);
      padding: 22px 28px 18px;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .subhead {{
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 12px 22px;
      font-size: 13px;
    }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 22px 28px 40px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr)) 2fr;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat, .panel, .issue {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .stat {{
      padding: 16px;
      border-left-width: 5px;
    }}
    .stat.critical {{ border-left-color: var(--critical); }}
    .stat.high {{ border-left-color: var(--high); }}
    .stat.medium {{ border-left-color: var(--medium); }}
    .stat.low {{ border-left-color: var(--low); }}
    .stat-value {{
      font-size: 30px;
      font-weight: 700;
      line-height: 1;
    }}
    .stat-label {{
      color: var(--muted);
      margin-top: 8px;
    }}
    .panel {{
      padding: 16px;
      margin-bottom: 16px;
    }}
    .panel h2 {{
      font-size: 16px;
      margin: 0 0 12px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #fff;
      font-size: 12px;
      color: #344054;
    }}
    .chip.signal {{
      border-color: #99d2cf;
      color: #005c64;
      background: #e9fbf8;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      margin: 18px 0;
    }}
    input[type="search"] {{
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 11px 12px;
      font-size: 15px;
      background: #fff;
    }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    button {{
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 8px;
      padding: 9px 12px;
      cursor: pointer;
      color: #344054;
      font-size: 14px;
    }}
    button.active {{
      color: #fff;
      background: var(--accent);
      border-color: var(--accent);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 18px;
      align-items: start;
    }}
    .issue {{
      margin-bottom: 12px;
      overflow: hidden;
    }}
    .issue-head {{
      display: grid;
      grid-template-columns: 96px minmax(0, 1fr) auto;
      gap: 12px;
      padding: 14px 16px;
      cursor: pointer;
      align-items: center;
      border-left: 6px solid var(--border);
    }}
    .issue[data-priority="critical"] .issue-head {{ border-left-color: var(--critical); background: var(--critical-bg); }}
    .issue[data-priority="high"] .issue-head {{ border-left-color: var(--high); background: var(--high-bg); }}
    .issue[data-priority="medium"] .issue-head {{ border-left-color: var(--medium); background: var(--medium-bg); }}
    .issue[data-priority="low"] .issue-head {{ border-left-color: var(--low); background: var(--low-bg); }}
    .badge {{
      display: inline-flex;
      justify-content: center;
      min-width: 72px;
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 13px;
      font-weight: 700;
      color: #fff;
    }}
    .badge.critical {{ background: var(--critical); }}
    .badge.high {{ background: var(--high); }}
    .badge.medium {{ background: var(--medium); }}
    .badge.low {{ background: var(--low); }}
    .issue-title {{
      min-width: 0;
    }}
    .issue-title strong {{
      display: block;
      font-size: 16px;
    }}
    .issue-title span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .issue-id {{
      color: var(--muted);
      font-size: 13px;
    }}
    .issue-body {{
      display: none;
      padding: 16px 18px 18px;
      background: #fff;
      border-top: 1px solid var(--border);
    }}
    .drawing-summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
      color: #344054;
      font-size: 13px;
    }}
    .mini-label {{
      color: var(--muted);
      display: block;
      margin-bottom: 2px;
    }}
    .finding {{
      border: 1px solid var(--border);
      border-radius: 8px;
      margin: 12px 0;
      overflow: hidden;
    }}
    .finding-head {{
      display: grid;
      grid-template-columns: 80px minmax(0, 1fr) auto;
      gap: 10px;
      padding: 10px 12px;
      background: #fbfcfe;
      align-items: center;
      border-bottom: 1px solid var(--border);
    }}
    .finding-body {{
      padding: 12px;
    }}
    .finding-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .finding-grid h4 {{
      margin: 0 0 6px;
      font-size: 13px;
      color: #344054;
    }}
    .finding-grid ul {{
      margin: 0;
    }}
    .issue.open .issue-body {{
      display: block;
    }}
    .issue-body h3 {{
      font-size: 14px;
      margin: 18px 0 8px;
      color: #344054;
    }}
    .issue-body h3:first-child {{ margin-top: 0; }}
    ol, ul {{
      margin-top: 8px;
      padding-left: 22px;
    }}
    li {{ margin-bottom: 6px; }}
    .evidence {{
      border: 1px solid var(--border);
      border-radius: 8px;
      margin: 10px 0;
      padding: 10px 12px;
      background: #fbfcfe;
    }}
    .evidence-title {{
      font-weight: 700;
      color: #344054;
      overflow-wrap: anywhere;
    }}
    .excerpt {{
      color: #344054;
      margin-top: 6px;
      font-size: 13px;
      white-space: pre-wrap;
    }}
    .side {{
      position: sticky;
      top: 102px;
    }}
    .notes {{
      white-space: pre-wrap;
      max-height: 560px;
      overflow: auto;
      font-size: 13px;
      color: #344054;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }}
    .low-docs {{
      max-height: 260px;
      overflow: auto;
      padding-left: 18px;
      font-size: 13px;
    }}
    .low-docs li {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      padding-bottom: 6px;
      border-bottom: 1px dashed #e4e7ec;
    }}
    .low-docs span {{
      overflow-wrap: anywhere;
    }}
    .empty {{
      display: none;
      text-align: center;
      padding: 36px;
      color: var(--muted);
      background: #fff;
      border: 1px dashed var(--border);
      border-radius: 8px;
    }}
    @media (max-width: 980px) {{
      header {{ position: static; }}
      .summary, .layout, .toolbar {{
        grid-template-columns: 1fr;
      }}
      .side {{ position: static; }}
      .issue-head {{
        grid-template-columns: 1fr;
      }}
      .drawing-summary, .finding-head, .finding-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AI-HAZOP 逐图纸预审仪表板</h1>
    <div class="subhead">
      <span>项目：{esc(metadata.get("project_name", "粤东LNG扩建项目"))}</span>
      <span>生成：{esc(metadata.get("generated_at", ""))}</span>
      <span>角色：参会专家问题筛查，不是主席结论</span>
    </div>
  </header>
  <main>
    <section class="summary">
      {stat_cards}
      <div class="panel" style="margin-bottom:0;">
        <h2>项目信号</h2>
        <div class="chips">{signal_items}</div>
      </div>
    </section>

    <section class="panel">
      <h2>文档类型命中</h2>
      <div class="chips">{doc_type_items}</div>
    </section>

    <section class="toolbar">
      <input id="search" type="search" placeholder="搜索图纸、设备位号、节点、问题、证据，例如 C0704 / BOG / ESD / 热膨胀">
      <div class="filters" aria-label="优先级筛选">
        <button class="active" data-filter="all">全部</button>
        <button data-filter="critical">关键</button>
        <button data-filter="high">高</button>
        <button data-filter="medium">中</button>
        <button data-filter="low">低</button>
      </div>
    </section>

    <section class="layout">
      <div>
        <div id="issue-list"></div>
        <div id="empty" class="empty">没有匹配的问题。</div>
      </div>
      <aside class="side">
        <section class="panel">
          <h2>红队复核摘要</h2>
          <div class="notes">{esc(red_team_notes)}</div>
        </section>
        <section class="panel">
          <h2>需人工看图优先关注</h2>
          <ul class="low-docs">{low_doc_items}</ul>
        </section>
      </aside>
    </section>
  </main>

  <script id="hazop-data" type="application/json">{script_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('hazop-data').textContent);
    const list = document.getElementById('issue-list');
    const empty = document.getElementById('empty');
    const search = document.getElementById('search');
    const buttons = [...document.querySelectorAll('button[data-filter]')];
    let activeFilter = 'all';

    function escapeHtml(value) {{
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function listItems(items, ordered = true) {{
      const tag = ordered ? 'ol' : 'ul';
      return `<${{tag}}>` + items.map(item => `<li>${{escapeHtml(item)}}</li>`).join('') + `</${{tag}}>`;
    }}

    function chipItems(items) {{
      return `<div class="chips">${{items.map(item => `<span class="chip">${{escapeHtml(item)}}</span>`).join('')}}</div>`;
    }}

    function evidenceItems(items) {{
      if (!items.length) return '<p class="muted">无证据摘录。</p>';
      return items.map(item => `
        <div class="evidence">
          <div class="evidence-title">${{escapeHtml(item.rel_path)}} · 关键词：${{escapeHtml(item.keyword)}}</div>
          <div class="excerpt">${{escapeHtml(item.excerpt)}}</div>
        </div>
      `).join('');
    }}

    function renderDrawingReviews(term) {{
      const html = data.drawingReviews.map((review, index) => {{
        const matchingFindings = review.findings.filter(finding => {{
          const priorityMatch = activeFilter === 'all' || finding.priority === activeFilter;
          const searchMatch = !term || review.searchText.includes(term) || finding.searchText.includes(term);
          return priorityMatch && searchMatch;
        }});
        const showEmptyDrawing = activeFilter === 'all' && !term && review.findings.length === 0;
        if (!matchingFindings.length && !showEmptyDrawing) return '';
        return `
          <article class="issue ${{index === 0 ? 'open' : ''}}" data-priority="${{escapeHtml(matchingFindings[0]?.priority || 'low')}}">
            <div class="issue-head" role="button" tabindex="0">
              <span class="badge ${{escapeHtml(matchingFindings[0]?.priority || 'low')}}">${{escapeHtml(matchingFindings[0]?.priorityLabel || '待看图')}}</span>
              <div class="issue-title">
                <strong>${{escapeHtml(review.drawingId)}} · ${{escapeHtml(review.title)}}</strong>
                <span>${{escapeHtml(review.relPath)}}</span>
              </div>
              <span class="issue-id">${{matchingFindings.length}} 行 · ${{escapeHtml(review.drawingNo)}}</span>
            </div>
            <div class="issue-body">
              <div class="drawing-summary">
                <div><span class="mini-label">节点提示</span>${{escapeHtml(review.nodeHint)}}</div>
                <div><span class="mini-label">抽取字符</span>${{escapeHtml(review.textChars)}}</div>
                <div><span class="mini-label">文档类型</span>${{escapeHtml(review.docTypes.join(', ') || '未识别')}}</div>
              </div>
              <h3>设计意图提示</h3>
              <p>${{escapeHtml(review.designIntentHint)}}</p>
              <h3>审查关注</h3>
              ${{chipItems(review.reviewFocus)}}
              ${{review.warnings.length ? `<h3>抽取警告</h3>${{listItems(review.warnings, false)}}` : ''}}
              ${{matchingFindings.length ? matchingFindings.map(finding => `
                <section class="finding">
                  <div class="finding-head">
                    <span class="badge ${{escapeHtml(finding.priority)}}">${{escapeHtml(finding.priorityLabel)}}</span>
                    <strong>${{escapeHtml(finding.id)}} · ${{escapeHtml(finding.parameter)}} · ${{escapeHtml(finding.analysisObject)}}</strong>
                    <span class="issue-id">${{escapeHtml(finding.sourceRule)}}</span>
                  </div>
                  <div class="finding-body">
                    <h3>问题/偏差</h3>
                    <p>${{escapeHtml(finding.problem)}}</p>
                    <div class="finding-grid">
                      <div><h4>可能原因（待确认）</h4>${{listItems(finding.possibleCauses, false)}}</div>
                      <div><h4>可能后果（待确认）</h4>${{listItems(finding.possibleConsequences, false)}}</div>
                      <div><h4>已有措施/保护层待核查</h4>${{listItems(finding.safeguardsToVerify, false)}}</div>
                      <div><h4>专家行动/需补证据</h4>${{listItems(finding.expertActions, false)}}</div>
                    </div>
                    ${{finding.relatedDocuments.length ? `<h3>必要时跨图核查</h3>${{listItems(finding.relatedDocuments, false)}}` : ''}}
                    <h3>本图纸证据摘录</h3>
                    ${{evidenceItems(finding.evidence)}}
                  </div>
                </section>
              `).join('') : '<p>本图纸未形成自动问题行，需人工看图确认节点边界、阀位、跨图连接和仪表联锁。</p>'}}
            </div>
          </article>
        `;
      }}).join('');
      list.innerHTML = html;
      return Boolean(html.trim());
    }}

    function renderIssueFallback(term) {{
      const filtered = data.issues.filter(issue => {{
        const priorityMatch = activeFilter === 'all' || issue.priority === activeFilter;
        const searchMatch = !term || issue.searchText.includes(term);
        return priorityMatch && searchMatch;
      }});

      list.innerHTML = filtered.map((issue, index) => `
        <article class="issue ${{index === 0 ? 'open' : ''}}" data-priority="${{escapeHtml(issue.priority)}}">
          <div class="issue-head" role="button" tabindex="0">
            <span class="badge ${{escapeHtml(issue.priority)}}">${{escapeHtml(issue.priorityLabel)}}</span>
            <div class="issue-title">
              <strong>${{escapeHtml(issue.topic)}}</strong>
              <span>${{escapeHtml(issue.node)}}</span>
            </div>
            <span class="issue-id">${{escapeHtml(issue.id)}} · ${{escapeHtml(issue.sourceRule)}}</span>
          </div>
          <div class="issue-body">
            <h3>关注点</h3>
            <p>${{escapeHtml(issue.concern)}}</p>
            <h3>建议会上提出</h3>
            ${{listItems(issue.questions)}}
            <h3>需要补充或定位的证据</h3>
            ${{chipItems(issue.requestedEvidence)}}
            <h3>导向词</h3>
            ${{chipItems(issue.guidewords)}}
            <h3>证据摘录</h3>
            ${{evidenceItems(issue.evidence)}}
          </div>
        </article>
      `).join('');
      return Boolean(filtered.length);
    }}

    function bindToggles() {{
      document.querySelectorAll('.issue-head').forEach(head => {{
        head.addEventListener('click', () => head.closest('.issue').classList.toggle('open'));
        head.addEventListener('keydown', event => {{
          if (event.key === 'Enter' || event.key === ' ') {{
            event.preventDefault();
            head.closest('.issue').classList.toggle('open');
          }}
        }});
      }});
    }}

    function render() {{
      const term = search.value.trim().toLowerCase();
      const hasRows = data.drawingReviews && data.drawingReviews.length
        ? renderDrawingReviews(term)
        : renderIssueFallback(term);
      empty.style.display = hasRows ? 'none' : 'block';
      bindToggles();
    }}

    buttons.forEach(button => {{
      button.addEventListener('click', () => {{
        buttons.forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        activeFilter = button.dataset.filter;
        render();
      }});
    }});

    search.addEventListener('input', render);
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an AI-HAZOP HTML dashboard.")
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    parser.add_argument("--red-team-notes", type=Path)
    args = parser.parse_args()

    data = load_json(args.input_json)
    red_team_notes = markdown_excerpt(args.red_team_notes)
    html_text = render_dashboard(data, red_team_notes)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_text, encoding="utf-8", newline="\n")
    print(f"Wrote HTML dashboard to: {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
