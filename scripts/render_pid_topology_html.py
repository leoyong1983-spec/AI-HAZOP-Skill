"""Render an offline HTML dashboard for vector-PDF P&ID topology evidence."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_package(package: dict[str, Any]) -> dict[str, Any]:
    docs = []
    total_segments = 0
    total_components = 0
    total_tags = 0
    total_connections = 0
    high_connections = 0
    for doc in package.get("documents", []):
        pages = []
        doc_connections = 0
        for page in doc.get("pages", []):
            components = []
            page_connections = 0
            for component in page.get("components", []):
                connections = component.get("connections", [])
                if not connections:
                    continue
                page_connections += len(connections)
                high_connections += sum(1 for c in connections if c.get("confidence") == "high")
                components.append({
                    "componentId": component.get("component_id", ""),
                    "bbox": component.get("bbox", []),
                    "orientation": component.get("orientation", ""),
                    "associatedText": component.get("associated_text", []),
                    "connections": connections,
                })
            total_segments += int(page.get("segment_count") or 0)
            total_components += int(page.get("component_count") or 0)
            total_tags += int(page.get("tag_count") or 0)
            total_connections += page_connections
            doc_connections += page_connections
            pages.append({
                "page": page.get("page", 0),
                "width": page.get("width", 0),
                "height": page.get("height", 0),
                "textCandidateCount": page.get("text_candidate_count", 0),
                "tagCount": page.get("tag_count", 0),
                "lineIdCount": page.get("line_id_count", 0),
                "segmentCount": page.get("segment_count", 0),
                "componentCount": page.get("component_count", 0),
                "components": components,
                "connectionCount": page_connections,
            })
        docs.append({
            "relPath": doc.get("rel_path", ""),
            "warnings": doc.get("warnings", []),
            "pages": pages,
            "connectionCount": doc_connections,
            "searchText": " ".join([
                str(doc.get("rel_path", "")),
                " ".join(
                    str(connection.get("from", "")) + " " + str(connection.get("to", ""))
                    for page in pages
                    for component in page["components"]
                    for connection in component["connections"]
                ),
            ]).lower(),
        })
    return {
        "metadata": package.get("metadata", {}),
        "summary": {
            "documentCount": len(docs),
            "skippedCount": len(package.get("skipped", [])),
            "totalSegments": total_segments,
            "totalComponents": total_components,
            "totalTags": total_tags,
            "totalConnections": total_connections,
            "highConnections": high_connections,
        },
        "documents": docs,
        "skipped": package.get("skipped", []),
    }


def safe_script_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("</", "<\\/")


def render_html(data: dict[str, Any]) -> str:
    script_json = safe_script_json(data)
    meta = data.get("metadata", {})
    summary = data.get("summary", {})
    limitations = "\n".join(f"<li>{esc(item)}</li>" for item in meta.get("limitations", []))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P&ID/PFD 拓扑证据检查</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #fff;
      --text: #1d2939;
      --muted: #667085;
      --border: #d9dee7;
      --accent: #006d77;
      --accent-soft: #e6f5f3;
      --high: #067647;
      --medium: #b54708;
      --weak: #475467;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      background: #fff;
      border-bottom: 1px solid var(--border);
      padding: 20px 28px 16px;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    h1 {{ margin: 0 0 8px; font-size: 24px; letter-spacing: 0; }}
    .subhead {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 20px;
      color: var(--muted);
      font-size: 13px;
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 20px 28px 40px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }}
    .stat, .panel, .doc {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .stat {{
      padding: 14px;
      border-left: 5px solid var(--accent);
    }}
    .stat b {{ display: block; font-size: 26px; line-height: 1; }}
    .stat span {{ display: block; margin-top: 7px; color: var(--muted); font-size: 13px; }}
    .panel {{ padding: 14px 16px; margin-bottom: 14px; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 16px; }}
    .limitations {{
      margin: 8px 0 0;
      padding-left: 20px;
      color: #344054;
      font-size: 13px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      margin: 16px 0;
      align-items: center;
    }}
    input[type="search"] {{
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 15px;
      background: #fff;
    }}
    .filters {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    button {{
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 8px;
      padding: 9px 12px;
      color: #344054;
      cursor: pointer;
      font-size: 14px;
    }}
    button.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    .doc {{ margin-bottom: 12px; overflow: hidden; }}
    .doc-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 13px 15px;
      cursor: pointer;
      background: #fbfcfe;
      border-left: 6px solid var(--accent);
    }}
    .doc-title strong {{ display: block; overflow-wrap: anywhere; }}
    .doc-title span {{ color: var(--muted); font-size: 13px; }}
    .doc-counts {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .pill {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      background: #fff;
      color: #344054;
    }}
    .doc-body {{
      display: none;
      padding: 15px;
      border-top: 1px solid var(--border);
      background: #fff;
    }}
    .doc.open .doc-body {{ display: block; }}
    .page {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .page-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }}
    .page-head h3 {{ margin: 0; font-size: 15px; }}
    .page-meta {{ color: var(--muted); font-size: 13px; }}
    .page-grid {{
      display: grid;
      grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.4fr);
      gap: 14px;
      align-items: start;
    }}
    .map {{
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f9fafb;
      overflow: hidden;
      min-height: 220px;
    }}
    svg {{ display: block; width: 100%; height: auto; }}
    .component {{
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 10px;
      overflow: hidden;
    }}
    .component-head {{
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      background: var(--accent-soft);
      padding: 9px 10px;
      border-bottom: 1px solid var(--border);
    }}
    .component-body {{ padding: 10px; }}
    .badge {{
      border-radius: 999px;
      color: #fff;
      padding: 4px 8px;
      font-size: 12px;
      text-align: center;
      font-weight: 700;
      background: var(--weak);
    }}
    .badge.high {{ background: var(--high); }}
    .badge.medium {{ background: var(--medium); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid #eaecf0;
      padding: 7px 6px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .tags {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .tag {{
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
    }}
    .empty {{
      display: none;
      padding: 32px;
      text-align: center;
      color: var(--muted);
      border: 1px dashed var(--border);
      border-radius: 8px;
      background: #fff;
    }}
    @media (max-width: 1000px) {{
      header {{ position: static; }}
      .stats, .toolbar, .page-grid, .doc-head, .component-head {{
        grid-template-columns: 1fr;
      }}
      .doc-counts {{ justify-content: flex-start; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>P&ID/PFD 拓扑证据检查</h1>
    <div class="subhead">
      <span>生成：{esc(meta.get("generated_at", ""))}</span>
      <span>方法：矢量PDF线段组件 + 位号近邻候选连接</span>
      <span>定位：拓扑证据，不是最终工艺结论</span>
    </div>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><b>{esc(summary.get("documentCount", 0))}</b><span>检查图纸</span></div>
      <div class="stat"><b>{esc(summary.get("skippedCount", 0))}</b><span>默认跳过</span></div>
      <div class="stat"><b>{esc(summary.get("totalSegments", 0))}</b><span>矢量线段</span></div>
      <div class="stat"><b>{esc(summary.get("totalComponents", 0))}</b><span>线段组件</span></div>
      <div class="stat"><b>{esc(summary.get("totalTags", 0))}</b><span>位号候选</span></div>
      <div class="stat"><b>{esc(summary.get("totalConnections", 0))}</b><span>候选连接</span></div>
    </section>

    <section class="panel">
      <h2>方法边界</h2>
      <ul class="limitations">{limitations}</ul>
      <p style="margin:10px 0 0;color:#344054;font-size:13px;">本页用于检查抽取工作是否有价值：同一矢量线段组件上靠近的位号会形成候选连接。它不能自动证明流向，也还不能识别阀门/设备符号语义。</p>
    </section>

    <section class="toolbar">
      <input id="search" type="search" placeholder="搜索图纸、位号或连接，例如 C0804A / C0904 / LT001 / BOG">
      <div class="filters">
        <button class="active" data-filter="all">全部</button>
        <button data-filter="high">高置信</button>
        <button data-filter="medium">中置信</button>
      </div>
    </section>

    <section id="doc-list"></section>
    <div id="empty" class="empty">没有匹配的拓扑证据。</div>
  </main>

  <script id="topology-data" type="application/json">{script_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('topology-data').textContent);
    const list = document.getElementById('doc-list');
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

    function connectionMatches(connection) {{
      return activeFilter === 'all' || connection.confidence === activeFilter;
    }}

    function docMatches(doc, term) {{
      if (!term) return true;
      return doc.searchText.includes(term);
    }}

    function mapSvg(page, components) {{
      const width = Number(page.width) || 1000;
      const height = Number(page.height) || 700;
      const shown = components.slice(0, 40);
      const rects = shown.map((component, index) => {{
        const b = component.bbox || [0,0,0,0];
        const color = component.connections.some(c => c.confidence === 'high') ? '#067647' : '#b54708';
        const label = component.componentId;
        return `
          <rect x="${{b[0]}}" y="${{b[1]}}" width="${{Math.max(2, b[2]-b[0])}}" height="${{Math.max(2, b[3]-b[1])}}"
            fill="none" stroke="${{color}}" stroke-width="5" opacity="0.8" />
          <text x="${{b[0]}}" y="${{Math.max(12, b[1]-6)}}" font-size="28" fill="${{color}}">${{escapeHtml(label)}}</text>
        `;
      }}).join('');
      return `<div class="map"><svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="组件位置小地图">
        <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="#f9fafb" />
        ${{rects}}
      </svg></div>`;
    }}

    function componentCard(component) {{
      const filteredConnections = component.connections.filter(connectionMatches);
      if (!filteredConnections.length) return '';
      const confidence = filteredConnections.some(c => c.confidence === 'high') ? 'high' : 'medium';
      const associated = component.associatedText || [];
      return `
        <article class="component">
          <div class="component-head">
            <span class="badge ${{confidence}}">${{confidence === 'high' ? '高置信' : '中置信'}}</span>
            <strong>${{escapeHtml(component.componentId)}} · ${{escapeHtml(component.orientation)}} · bbox ${{escapeHtml((component.bbox || []).join(', '))}}</strong>
            <span class="pill">${{filteredConnections.length}} 条连接</span>
          </div>
          <div class="component-body">
            <table>
              <thead><tr><th>From</th><th>To</th><th>置信度</th><th>距离</th><th>依据</th></tr></thead>
              <tbody>
                ${{filteredConnections.map(c => `
                  <tr>
                    <td>${{escapeHtml(c.from)}}</td>
                    <td>${{escapeHtml(c.to)}}</td>
                    <td>${{escapeHtml(c.confidence)}}</td>
                    <td>${{escapeHtml(c.from_distance)}} / ${{escapeHtml(c.to_distance)}}</td>
                    <td>${{escapeHtml(c.reason)}}</td>
                  </tr>
                `).join('')}}
              </tbody>
            </table>
            <div class="tags">
              ${{associated.slice(0, 16).map(item => `<span class="tag">${{escapeHtml(item.text)}} · ${{escapeHtml(item.kind)}} · d=${{escapeHtml(item.distance)}}</span>`).join('')}}
            </div>
          </div>
        </article>
      `;
    }}

    function pageBlock(page) {{
      const components = page.components
        .map(component => ({{...component, connections: component.connections.filter(connectionMatches)}}))
        .filter(component => component.connections.length);
      if (!components.length) return '';
      const connectionCount = components.reduce((sum, component) => sum + component.connections.length, 0);
      return `
        <section class="page">
          <div class="page-head">
            <h3>第 ${{escapeHtml(page.page)}} 页</h3>
            <div class="page-meta">位号 ${{escapeHtml(page.tagCount)}} · 线段 ${{escapeHtml(page.segmentCount)}} · 组件 ${{escapeHtml(page.componentCount)}} · 当前连接 ${{connectionCount}}</div>
          </div>
          <div class="page-grid">
            ${{mapSvg(page, components)}}
            <div>${{components.map(componentCard).join('')}}</div>
          </div>
        </section>
      `;
    }}

    function docBlock(doc, index, term) {{
      if (!docMatches(doc, term)) return '';
      const pagesHtml = doc.pages.map(pageBlock).join('');
      if (!pagesHtml) return '';
      const connectionCount = doc.pages.flatMap(p => p.components).flatMap(c => c.connections).filter(connectionMatches).length;
      return `
        <article class="doc ${{index === 0 ? 'open' : ''}}">
          <div class="doc-head" role="button" tabindex="0">
            <div class="doc-title">
              <strong>${{escapeHtml(doc.relPath)}}</strong>
              <span>${{doc.warnings.length ? '警告：' + escapeHtml(doc.warnings.join('；')) : '矢量PDF拓扑证据'}}</span>
            </div>
            <div class="doc-counts">
              <span class="pill">${{connectionCount}} 条连接</span>
              <span class="pill">${{doc.pages.length}} 页</span>
            </div>
          </div>
          <div class="doc-body">${{pagesHtml}}</div>
        </article>
      `;
    }}

    function bindToggles() {{
      document.querySelectorAll('.doc-head').forEach(head => {{
        head.addEventListener('click', () => head.closest('.doc').classList.toggle('open'));
        head.addEventListener('keydown', event => {{
          if (event.key === 'Enter' || event.key === ' ') {{
            event.preventDefault();
            head.closest('.doc').classList.toggle('open');
          }}
        }});
      }});
    }}

    function render() {{
      const term = search.value.trim().toLowerCase();
      const html = data.documents.map((doc, index) => docBlock(doc, index, term)).join('');
      list.innerHTML = html;
      empty.style.display = html.trim() ? 'none' : 'block';
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
    parser = argparse.ArgumentParser(description="Render P&ID topology evidence as an offline HTML dashboard.")
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    args = parser.parse_args()

    package = load_json(args.input_json)
    compact = compact_package(package)
    html_text = render_html(compact)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_text, encoding="utf-8", newline="\n")
    print(f"Wrote topology HTML dashboard to: {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
