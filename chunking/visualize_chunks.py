#!/usr/bin/env python3
"""
Visualize Document AI Layout Parser Chunks on the Input PDF.

- Reads the input PDF and Document AI JSON output (auto-detected from manifest or .env).
- Renders PDF pages into embedded images.
- Extracts chunks, block hierarchies, and bounding box coordinates.
- Generates a standalone, interactive HTML dashboard with synchronized overlays.
"""

import argparse
import base64
from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import pymupdf


# 20 distinct, aesthetically balanced colors for chunks
CHUNK_COLORS = [
    {"hex": "#2563EB", "rgba": "rgba(37, 99, 235, 0.22)", "border": "rgba(37, 99, 235, 0.9)"},      # Blue
    {"hex": "#059669", "rgba": "rgba(5, 150, 105, 0.22)", "border": "rgba(5, 150, 105, 0.9)"},      # Emerald
    {"hex": "#D97706", "rgba": "rgba(217, 119, 6, 0.22)", "border": "rgba(217, 119, 6, 0.9)"},      # Amber
    {"hex": "#DC2626", "rgba": "rgba(220, 38, 38, 0.22)", "border": "rgba(220, 38, 38, 0.9)"},      # Red
    {"hex": "#7C3AED", "rgba": "rgba(124, 58, 237, 0.22)", "border": "rgba(124, 58, 237, 0.9)"},   # Purple
    {"hex": "#0891B2", "rgba": "rgba(8, 145, 178, 0.22)", "border": "rgba(8, 145, 178, 0.9)"},      # Cyan
    {"hex": "#DB2777", "rgba": "rgba(219, 39, 119, 0.22)", "border": "rgba(219, 39, 119, 0.9)"},   # Pink
    {"hex": "#4F46E5", "rgba": "rgba(79, 70, 229, 0.22)", "border": "rgba(79, 70, 229, 0.9)"},      # Indigo
    {"hex": "#16A34A", "rgba": "rgba(22, 163, 74, 0.22)", "border": "rgba(22, 163, 74, 0.9)"},      # Green
    {"hex": "#EA580C", "rgba": "rgba(234, 88, 12, 0.22)", "border": "rgba(234, 88, 12, 0.9)"},      # Orange
    {"hex": "#9333EA", "rgba": "rgba(147, 51, 234, 0.22)", "border": "rgba(147, 51, 234, 0.9)"},   # Violet
    {"hex": "#0D9488", "rgba": "rgba(13, 148, 136, 0.22)", "border": "rgba(13, 148, 136, 0.9)"},   # Teal
    {"hex": "#C026D3", "rgba": "rgba(192, 38, 211, 0.22)", "border": "rgba(192, 38, 211, 0.9)"},   # Fuchsia
    {"hex": "#475569", "rgba": "rgba(71, 85, 105, 0.22)", "border": "rgba(71, 85, 105, 0.9)"},      # Slate
    {"hex": "#0284C7", "rgba": "rgba(2, 132, 199, 0.22)", "border": "rgba(2, 132, 199, 0.9)"},      # Light Blue
    {"hex": "#65A30D", "rgba": "rgba(101, 163, 13, 0.22)", "border": "rgba(101, 163, 13, 0.9)"},   # Lime
    {"hex": "#B45309", "rgba": "rgba(180, 83, 9, 0.22)", "border": "rgba(180, 83, 9, 0.9)"},        # Warm Amber
    {"hex": "#E11D48", "rgba": "rgba(225, 29, 72, 0.22)", "border": "rgba(225, 29, 72, 0.9)"},      # Rose
    {"hex": "#4338CA", "rgba": "rgba(67, 56, 202, 0.22)", "border": "rgba(67, 56, 202, 0.9)"},      # Deep Indigo
    {"hex": "#047857", "rgba": "rgba(4, 120, 87, 0.22)", "border": "rgba(4, 120, 87, 0.9)"},       # Emerald Dark
]


def load_env_or_manifest() -> Dict[str, str]:
    """Retrieve default paths from manifest.json, .env, or default locations."""
    load_dotenv()
    local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "./results")
    manifest_file = os.path.join(local_output_dir, "manifest.json")

    pdf_path = ""
    json_path = ""
    output_html = os.getenv("DASHBOARD_HTML_PATH", os.path.join(local_output_dir, "dashboard.html"))

    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                pdf_path = manifest.get("pdf_path", "")
                json_path = manifest.get("primary_json", "")
        except Exception:
            pass

    if not pdf_path:
        pdf_path = os.getenv("INPUT_FILE_PATH", "")

    if not json_path and os.path.exists(local_output_dir):
        # Pick the most recently modified json in results (excluding manifest.json)
        json_candidates = [
            os.path.join(local_output_dir, f)
            for f in os.listdir(local_output_dir)
            if f.endswith(".json") and f != "manifest.json"
        ]
        if json_candidates:
            json_candidates.sort(key=os.path.getmtime, reverse=True)
            json_path = json_candidates[0]

    return {
        "pdf_path": pdf_path,
        "json_path": json_path,
        "output_html": output_html,
    }


def parse_arguments(defaults: Dict[str, str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML dashboard visualizing Document AI chunks overlaid on the PDF."
    )
    parser.add_argument(
        "--pdf",
        default=defaults["pdf_path"],
        help="Path to input PDF file (auto-detected from manifest or .env if omitted)",
    )
    parser.add_argument(
        "--json",
        default=defaults["json_path"],
        help="Path to Document AI output JSON file (auto-detected if omitted)",
    )
    parser.add_argument(
        "--output",
        default=defaults["output_html"],
        help="Path for generated HTML dashboard (default: ./results/dashboard.html)",
    )
    return parser.parse_args()


def extract_all_blocks(blocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Recursively traverses documentLayout blocks and indexes them by blockId."""
    blocks_map = {}

    def _traverse(block: Dict[str, Any]):
        bid = str(block.get("blockId", ""))
        if bid:
            blocks_map[bid] = block

        # Recurse into text blocks
        tb = block.get("textBlock")
        if isinstance(tb, dict) and "blocks" in tb:
            for child in tb["blocks"]:
                _traverse(child)

        # Recurse into list blocks
        lb = block.get("listBlock")
        if isinstance(lb, dict) and "listEntries" in lb:
            for entry in lb["listEntries"]:
                if isinstance(entry, dict) and "blocks" in entry:
                    for child in entry["blocks"]:
                        _traverse(child)

    for b in blocks:
        _traverse(b)

    return blocks_map


def get_block_type_label(block: Dict[str, Any]) -> str:
    """Returns a short human-readable block type (heading, paragraph, table, list, image)."""
    if "textBlock" in block:
        tb = block["textBlock"]
        return tb.get("type", "text")
    if "tableBlock" in block:
        return "table"
    if "listBlock" in block:
        return "list"
    if "imageBlock" in block:
        return "image"
    return "block"


def parse_docai_output(json_path: str) -> Tuple[List[Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
    """
    Parses Document AI Layout Parser JSON output.
    Returns:
      chunks_list: List of enriched chunk dictionaries.
      page_overlays: Map of page_number (1-indexed) -> list of bounding box overlay descriptors.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        doc_data = json.load(f)

    # 1. Index all layout blocks
    raw_blocks = doc_data.get("documentLayout", {}).get("blocks", [])
    blocks_map = extract_all_blocks(raw_blocks)

    # 2. Extract chunks
    raw_chunks = doc_data.get("chunkedDocument", {}).get("chunks", [])
    if not raw_chunks:
        print("[Warning] No chunks found in chunkedDocument. Checking document.entities or text...")

    chunks_list = []
    page_overlays: Dict[int, List[Dict[str, Any]]] = {}

    for idx, c in enumerate(raw_chunks):
        chunk_id = c.get("chunkId", f"c{idx+1}")
        content = c.get("content", "")
        page_span = c.get("pageSpan", {})
        page_start = page_span.get("pageStart", 1)
        page_end = page_span.get("pageEnd", page_start)
        source_block_ids = [str(bid) for bid in c.get("sourceBlockIds", [])]
        color = CHUNK_COLORS[idx % len(CHUNK_COLORS)]

        # Extract headings from content (e.g. lines starting with #)
        headings = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("#"):
                clean_heading = re.sub(r"^#+\s*", "", line_str)
                if clean_heading and clean_heading not in headings:
                    headings.append(clean_heading)

        # Estimate tokens (rough approximation: 1 token ~ 4 chars / 0.75 words)
        words = content.split()
        estimated_tokens = max(1, int(len(words) * 1.3))

        chunk_info = {
            "chunk_id": chunk_id,
            "index": idx,
            "color": color,
            "page_start": page_start,
            "page_end": page_end,
            "page_span_str": f"Page {page_start}" if page_start == page_end else f"Pages {page_start}–{page_end}",
            "source_block_ids": source_block_ids,
            "headings": headings[:3],  # top 3 headings
            "estimated_tokens": estimated_tokens,
            "char_count": len(content),
            "content": content,
        }
        chunks_list.append(chunk_info)

        # Map source blocks to pages and bounding boxes
        for bid in source_block_ids:
            blk = blocks_map.get(bid)
            if not blk:
                continue

            blk_span = blk.get("pageSpan", {})
            blk_pstart = blk_span.get("pageStart", page_start)
            blk_pend = blk_span.get("pageEnd", blk_pstart)
            blk_type = get_block_type_label(blk)

            bbox = blk.get("boundingBox", {})
            norm_verts = bbox.get("normalizedVertices", [])

            if norm_verts and len(norm_verts) >= 2:
                xs = [v.get("x", 0.0) for v in norm_verts]
                ys = [v.get("y", 0.0) for v in norm_verts]
                min_x = max(0.0, min(xs))
                max_x = min(1.0, max(xs))
                min_y = max(0.0, min(ys))
                max_y = min(1.0, max(ys))

                width = max_x - min_x
                height = max_y - min_y

                # Avoid degenerate boxes
                if width > 0.001 and height > 0.001:
                    # Place on each page in block page span
                    for p in range(blk_pstart, blk_pend + 1):
                        page_overlays.setdefault(p, []).append({
                            "chunk_id": chunk_id,
                            "chunk_index": idx,
                            "block_id": bid,
                            "block_type": blk_type,
                            "color": color,
                            "left": round(min_x * 100, 3),
                            "top": round(min_y * 100, 3),
                            "width": round(width * 100, 3),
                            "height": round(height * 100, 3),
                        })

    return chunks_list, page_overlays


def render_pdf_pages_to_images(pdf_path: str, max_dimension: int = 1400) -> List[Dict[str, Any]]:
    """
    Renders PDF pages into JPEG base64 strings with dimensions and aspect ratios.
    Optimized for fast rendering and minimal HTML file size.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist at: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    rendered_pages = []

    print(f"[PDF] Rendering {len(doc)} pages from {pdf_path}...")
    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        scale = min(float(max_dimension) / max(rect.width, rect.height), 2.0)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix)
        jpg_bytes = pix.tobytes("jpeg", jpg_quality=85)
        b64_str = base64.b64encode(jpg_bytes).decode("utf-8")

        rendered_pages.append({
            "page_number": page_num + 1,  # 1-indexed
            "width": pix.width,
            "height": pix.height,
            "aspect_ratio": round(pix.height / pix.width, 4),
            "data_uri": f"data:image/jpeg;base64,{b64_str}",
        })

    return rendered_pages


def generate_html_dashboard(
    pdf_filename: str,
    chunks: List[Dict[str, Any]],
    page_overlays: Dict[int, List[Dict[str, Any]]],
    pages: List[Dict[str, Any]],
    output_path: str,
):
    """Generates the interactive single-file HTML dashboard."""
    total_tokens = sum(c["estimated_tokens"] for c in chunks)
    avg_tokens = round(total_tokens / len(chunks)) if chunks else 0
    total_pages = len(pages)
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Serialize JSON data for embedded JS
    chunks_json = json.dumps(chunks)
    pages_meta_json = json.dumps([
        {"page_number": p["page_number"], "width": p["width"], "height": p["height"]}
        for p in pages
    ])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document AI Chunking Dashboard - {pdf_filename}</title>
  <style>
    :root {{
      --bg-primary: #f8fafc;
      --bg-surface: #ffffff;
      --bg-secondary: #f1f5f9;
      --border-color: #e2e8f0;
      --text-primary: #0f172a;
      --text-secondary: #475569;
      --text-muted: #94a3b8;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --radius: 8px;
      --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
      --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
      --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-primary);
      color: var(--text-primary);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}

    /* Top Navigation Bar */
    header {{
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-shrink: 0;
      z-index: 20;
    }}

    .header-left {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .brand-logo {{
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, #2563eb, #7c3aed);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 700;
      font-size: 15px;
    }}

    .doc-info {{
      display: flex;
      flex-direction: column;
    }}

    .doc-title {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
      max-width: 380px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .doc-subtitle {{
      font-size: 12px;
      color: var(--text-muted);
    }}

    .stats-bar {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .stat-badge {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 5px;
    }}

    .stat-badge strong {{
      color: var(--text-primary);
    }}

    .header-right {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    /* Main Container (Split Screen) */
    .dashboard-container {{
      flex: 1;
      display: flex;
      overflow: hidden;
    }}

    /* Left Panel: PDF Viewer */
    .viewer-panel {{
      flex: 1.4;
      display: flex;
      flex-direction: column;
      background: #cbd5e1;
      border-right: 1px solid var(--border-color);
      overflow: hidden;
    }}

    .viewer-controls {{
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: 8px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
    }}

    .control-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .btn {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 5px 10px;
      border-radius: var(--radius);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s ease;
    }}

    .btn:hover {{
      background: var(--bg-secondary);
      border-color: #cbd5e1;
    }}

    .btn-primary {{
      background: var(--primary);
      border-color: var(--primary);
      color: white;
    }}

    .btn-primary:hover {{
      background: var(--primary-hover);
    }}

    .checkbox-label {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--text-secondary);
      cursor: pointer;
      user-select: none;
    }}

    .viewer-scroll {{
      flex: 1;
      overflow-y: auto;
      overflow-x: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 28px;
    }}

    /* Page Canvas Card */
    .page-wrapper {{
      display: flex;
      flex-direction: column;
      align-items: center;
      max-width: 100%;
    }}

    .page-header {{
      width: 100%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
      padding: 0 4px;
      font-size: 12px;
      font-weight: 600;
      color: #334155;
    }}

    .page-container {{
      position: relative;
      background: white;
      box-shadow: var(--shadow-lg);
      border-radius: 4px;
      overflow: hidden;
      line-height: 0;
      user-select: none;
      transition: transform 0.15s ease;
    }}

    .page-image {{
      display: block;
      width: 100%;
      height: auto;
      pointer-events: none;
    }}

    .overlay-layer {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: auto;
    }}

    /* Bounding Box Overlays */
    .chunk-box {{
      position: absolute;
      border-radius: 3px;
      box-sizing: border-box;
      cursor: pointer;
      transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
      z-index: 5;
    }}

    .chunk-box:hover,
    .chunk-box.active {{
      z-index: 10;
      box-shadow: 0 0 0 2px white, 0 0 10px rgba(0,0,0,0.3);
    }}

    .chunk-badge-tag {{
      position: absolute;
      top: -10px;
      left: -2px;
      color: white;
      font-size: 10px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 3px;
      box-shadow: var(--shadow-sm);
      pointer-events: none;
      z-index: 12;
      line-height: 1.2;
    }}

    /* Floating Tooltip */
    #hover-tooltip {{
      position: fixed;
      display: none;
      background: #1e293b;
      color: #f8fafc;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 12px;
      max-width: 280px;
      pointer-events: none;
      z-index: 1000;
      box-shadow: var(--shadow-lg);
      line-height: 1.4;
    }}

    /* Right Panel: Chunks Explorer */
    .chunks-panel {{
      flex: 1;
      display: flex;
      flex-direction: column;
      background: var(--bg-surface);
      overflow: hidden;
    }}

    .panel-header {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: var(--bg-surface);
      z-index: 10;
    }}

    .panel-title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .panel-title {{
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-secondary);
    }}

    .search-input {{
      width: 100%;
      padding: 7px 12px;
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s ease;
    }}

    .search-input:focus {{
      border-color: var(--primary);
    }}

    .filter-pills {{
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}

    .filter-pill {{
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;
      border: 1px solid var(--border-color);
      background: var(--bg-secondary);
      color: var(--text-secondary);
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }}

    .filter-pill.active {{
      background: var(--primary);
      color: white;
      border-color: var(--primary);
    }}

    /* Chunks List */
    .chunks-list {{
      flex: 1;
      overflow-y: auto;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .chunk-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 12px;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .chunk-card:hover {{
      transform: translateY(-1px);
      box-shadow: var(--shadow-md);
      border-color: #94a3b8;
    }}

    .chunk-card.active {{
      border-width: 2px;
      box-shadow: var(--shadow-md);
    }}

    .card-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .chunk-id-tag {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-weight: 700;
      font-size: 13px;
    }}

    .color-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    .badge-group {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .pill {{
      font-size: 11px;
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 4px;
      background: var(--bg-secondary);
      color: var(--text-secondary);
    }}

    .headings-container {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }}

    .heading-tag {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1d4ed8;
      font-size: 11px;
      padding: 2px 6px;
      border-radius: 4px;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .chunk-content-preview {{
      font-size: 12px;
      line-height: 1.5;
      color: var(--text-secondary);
      background: var(--bg-secondary);
      padding: 8px 10px;
      border-radius: 6px;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      max-height: 110px;
      overflow: hidden;
      position: relative;
    }}

    .chunk-content-preview.expanded {{
      max-height: none;
    }}

    .card-actions {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 2px;
    }}

    .toggle-expand-btn {{
      font-size: 11px;
      color: var(--primary);
      background: none;
      border: none;
      cursor: pointer;
      font-weight: 600;
      padding: 0;
    }}

    .copy-btn {{
      font-size: 11px;
      color: var(--text-muted);
      background: none;
      border: 1px solid var(--border-color);
      border-radius: 4px;
      padding: 2px 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }}

    .copy-btn:hover {{
      color: var(--text-primary);
      background: var(--bg-secondary);
    }}

    /* Empty state */
    .empty-state {{
      text-align: center;
      padding: 40px 20px;
      color: var(--text-muted);
      font-size: 13px;
    }}

    /* Highlight pulse animation */
    @keyframes pulse-ring {{
      0% {{
        box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7);
      }}
      70% {{
        box-shadow: 0 0 0 10px rgba(37, 99, 235, 0);
      }}
      100% {{
        box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
      }}
    }}

    .pulse {{
      animation: pulse-ring 1.2s cubic-bezier(0.24, 0, 0.38, 1) infinite;
    }}
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="header-left">
      <div class="brand-logo">AI</div>
      <div class="doc-info">
        <span class="doc-title" title="{pdf_filename}">{pdf_filename}</span>
        <span class="doc-subtitle">Gemini Layout Parser &bull; Context-Aware Chunks &bull; Generated {timestamp_str}</span>
      </div>
    </div>

    <div class="stats-bar">
      <div class="stat-badge">
        <span>Chunks:</span>
        <strong id="stat-total-chunks">{len(chunks)}</strong>
      </div>
      <div class="stat-badge">
        <span>Pages:</span>
        <strong>{total_pages}</strong>
      </div>
      <div class="stat-badge">
        <span>Total Tokens:</span>
        <strong>~{total_tokens}</strong>
      </div>
      <div class="stat-badge">
        <span>Avg Tokens/Chunk:</span>
        <strong>~{avg_tokens}</strong>
      </div>
    </div>

    <div class="header-right">
      <button class="btn" id="btn-reset">Reset View</button>
    </div>
  </header>

  <!-- Main Container -->
  <div class="dashboard-container">
    
    <!-- Left Panel: PDF Viewer with Overlays -->
    <div class="viewer-panel">
      <div class="viewer-controls">
        <div class="control-group">
          <label class="checkbox-label">
            <input type="checkbox" id="toggle-boxes" checked>
            <span>Show Chunk Overlays</span>
          </label>
          <label class="checkbox-label" style="margin-left: 10px;">
            <input type="checkbox" id="toggle-badges" checked>
            <span>Show ID Badges</span>
          </label>
        </div>

        <div class="control-group">
          <span>Page:</span>
          <select id="page-select" class="btn" style="padding: 3px 6px;">
            <option value="all">All Pages ({total_pages})</option>
            {"".join(f'<option value="{p["page_number"]}">Page {p["page_number"]}</option>' for p in pages)}
          </select>
          <button class="btn" id="btn-zoom-out" title="Zoom Out">&minus;</button>
          <span id="zoom-label" style="font-weight: 600; font-size: 11px; min-width: 36px; text-align: center;">100%</span>
          <button class="btn" id="btn-zoom-in" title="Zoom In">&plus;</button>
        </div>
      </div>

      <div class="viewer-scroll" id="viewer-scroll">
        <!-- Loop over rendered PDF pages -->
"""

    # Generate page DOM elements
    for p in pages:
        pnum = p["page_number"]
        pw = p["width"]
        ph = p["height"]
        data_uri = p["data_uri"]
        overlays = page_overlays.get(pnum, [])

        html_content += f"""
        <div class="page-wrapper" id="page-wrapper-{pnum}" data-page="{pnum}">
          <div class="page-header">
            <span>Page {pnum} of {total_pages}</span>
            <span style="color: #64748b; font-weight: 400;">{len(overlays)} blocks</span>
          </div>
          <div class="page-container" id="page-container-{pnum}" style="max-width: 900px; width: 100%;">
            <img src="{data_uri}" class="page-image" alt="Page {pnum}">
            <div class="overlay-layer" id="overlay-layer-{pnum}">
        """

        # Overlays for this page
        for box in overlays:
            cid = box["chunk_id"]
            cidx = box["chunk_index"]
            c_color = box["color"]
            left = box["left"]
            top = box["top"]
            width = box["width"]
            height = box["height"]
            btype = box["block_type"]
            bid = box["block_id"]

            html_content += f"""
              <div class="chunk-box chunk-{cid}"
                   data-chunk-id="{cid}"
                   data-chunk-index="{cidx}"
                   data-page="{pnum}"
                   data-block-id="{bid}"
                   data-block-type="{btype}"
                   style="left: {left}%; top: {top}%; width: {width}%; height: {height}%; background-color: {c_color['rgba']}; border: 2px solid {c_color['border']};">
                <span class="chunk-badge-tag" style="background-color: {c_color['hex']};">{cid}</span>
              </div>
            """

        html_content += """
            </div>
          </div>
        </div>
        """

    html_content += f"""
      </div>
    </div>

    <!-- Right Panel: Chunks List -->
    <div class="chunks-panel">
      <div class="panel-header">
        <div class="panel-title-row">
          <span class="panel-title">Extracted Chunks ({len(chunks)})</span>
          <span id="filtered-count" style="font-size: 12px; color: var(--text-muted);"></span>
        </div>
        <input type="text" id="chunk-search" class="search-input" placeholder="Search chunk content, headings, or ID...">
        <div class="filter-pills" id="page-filter-pills">
          <div class="filter-pill active" data-page-filter="all">All ({len(chunks)})</div>
          {"".join(f'<div class="filter-pill" data-page-filter="{p["page_number"]}">P{p["page_number"]}</div>' for p in pages)}
        </div>
      </div>

      <div class="chunks-list" id="chunks-list">
"""

    # Generate chunk cards
    for c in chunks:
        cid = c["chunk_id"]
        cidx = c["index"]
        c_color = c["color"]
        page_span_str = c["page_span_str"]
        tokens = c["estimated_tokens"]
        chars = c["char_count"]
        headings = c["headings"]
        content_escaped = (
            c["content"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

        headings_html = ""
        if headings:
            headings_html = '<div class="headings-container">' + "".join(
                f'<span class="heading-tag" title="{h}"># {h}</span>' for h in headings
            ) + '</div>'

        html_content += f"""
        <div class="chunk-card" id="card-{cid}" data-chunk-id="{cid}" data-chunk-index="{cidx}" data-start-page="{c['page_start']}" data-end-page="{c['page_end']}" style="border-left: 4px solid {c_color['hex']};">
          <div class="card-top">
            <div class="chunk-id-tag">
              <span class="color-dot" style="background-color: {c_color['hex']};"></span>
              <span>{cid}</span>
            </div>
            <div class="badge-group">
              <span class="pill">{page_span_str}</span>
              <span class="pill">~{tokens} tokens</span>
            </div>
          </div>

          {headings_html}

          <div class="chunk-content-preview" id="content-{cid}">{content_escaped}</div>

          <div class="card-actions">
            <button class="toggle-expand-btn" data-target="content-{cid}">Expand full text &darr;</button>
            <button class="copy-btn" data-copy-id="content-{cid}">Copy text</button>
          </div>
        </div>
        """

    html_content += f"""
      </div>
    </div>
  </div>

  <!-- Floating Hover Tooltip -->
  <div id="hover-tooltip"></div>

  <!-- Interactive JavaScript -->
  <script>
    const CHUNKS_DATA = {chunks_json};
    const PAGES_DATA = {pages_meta_json};

    let currentZoom = 1.0;
    let activeChunkId = null;

    // Elements
    const viewerScroll = document.getElementById("viewer-scroll");
    const pageSelect = document.getElementById("page-select");
    const toggleBoxes = document.getElementById("toggle-boxes");
    const toggleBadges = document.getElementById("toggle-badges");
    const chunkSearch = document.getElementById("chunk-search");
    const chunksList = document.getElementById("chunks-list");
    const tooltip = document.getElementById("hover-tooltip");
    const btnZoomIn = document.getElementById("btn-zoom-in");
    const btnZoomOut = document.getElementById("btn-zoom-out");
    const zoomLabel = document.getElementById("zoom-label");
    const btnReset = document.getElementById("btn-reset");

    // 1. Zoom Controls
    function setZoom(val) {{
      currentZoom = Math.min(Math.max(val, 0.6), 2.2);
      zoomLabel.textContent = Math.round(currentZoom * 100) + "%";
      document.querySelectorAll(".page-container").forEach(el => {{
        el.style.transform = `scale(${{currentZoom}})`;
        el.style.transformOrigin = "top center";
      }});
      // Adjust wrapper margin for zoom
      document.querySelectorAll(".page-wrapper").forEach(el => {{
        const h = el.querySelector(".page-container").offsetHeight;
        if (currentZoom > 1.0) {{
          el.style.marginBottom = (h * (currentZoom - 1) + 28) + "px";
        }} else {{
          el.style.marginBottom = "0px";
        }}
      }});
    }}

    btnZoomIn.addEventListener("click", () => setZoom(currentZoom + 0.15));
    btnZoomOut.addEventListener("click", () => setZoom(currentZoom - 0.15));

    // 2. Page Navigation
    pageSelect.addEventListener("change", (e) => {{
      const p = e.target.value;
      if (p === "all") {{
        document.querySelectorAll(".page-wrapper").forEach(el => el.style.display = "flex");
      }} else {{
        document.querySelectorAll(".page-wrapper").forEach(el => {{
          el.style.display = (el.dataset.page === p) ? "flex" : "none";
        }});
        const targetPage = document.getElementById("page-wrapper-" + p);
        if (targetPage) targetPage.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }});

    // 3. Toggle Overlays & Badges
    toggleBoxes.addEventListener("change", (e) => {{
      document.querySelectorAll(".chunk-box").forEach(el => {{
        el.style.display = e.target.checked ? "block" : "none";
      }});
    }});

    toggleBadges.addEventListener("change", (e) => {{
      document.querySelectorAll(".chunk-badge-tag").forEach(el => {{
        el.style.display = e.target.checked ? "block" : "none";
      }});
    }});

    // 4. Bi-directional Highlighting & Navigation
    function highlightChunk(chunkId, scrollPdf = false, scrollSidebar = false) {{
      activeChunkId = chunkId;

      // Clear previous active states
      document.querySelectorAll(".chunk-card").forEach(c => {{
        c.classList.remove("active");
        c.style.borderColor = "";
      }});
      document.querySelectorAll(".chunk-box").forEach(b => {{
        b.classList.remove("active");
        b.classList.remove("pulse");
      }});

      if (!chunkId) return;

      // Highlight card
      const card = document.getElementById("card-" + chunkId);
      if (card) {{
        card.classList.add("active");
        const chunkObj = CHUNKS_DATA.find(c => c.chunk_id === chunkId);
        if (chunkObj) card.style.borderColor = chunkObj.color.hex;
        if (scrollSidebar) {{
          card.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
        }}
      }}

      // Highlight boxes on PDF
      const boxes = document.querySelectorAll(`.chunk-box[data-chunk-id="${{chunkId}}"]`);
      boxes.forEach(b => {{
        b.classList.add("active");
      }});

      if (scrollPdf && boxes.length > 0) {{
        const firstBox = boxes[0];
        const pageNum = firstBox.dataset.page;
        // If single-page view filtered, switch select
        if (pageSelect.value !== "all" && pageSelect.value !== pageNum) {{
          pageSelect.value = "all";
          document.querySelectorAll(".page-wrapper").forEach(el => el.style.display = "flex");
        }}
        firstBox.classList.add("pulse");
        firstBox.scrollIntoView({{ behavior: "smooth", block: "center" }});
      }}
    }}

    // Chunk Card interactions
    document.querySelectorAll(".chunk-card").forEach(card => {{
      const cid = card.dataset.chunkId;
      card.addEventListener("mouseenter", () => highlightChunk(cid, false, false));
      card.addEventListener("click", () => highlightChunk(cid, true, false));
    }});

    // Bounding Box interactions
    document.querySelectorAll(".chunk-box").forEach(box => {{
      const cid = box.dataset.chunkId;
      const btype = box.dataset.blockType;

      box.addEventListener("mouseenter", (e) => {{
        highlightChunk(cid, false, true);

        const chunkObj = CHUNKS_DATA.find(c => c.chunk_id === cid);
        if (chunkObj) {{
          tooltip.innerHTML = `
            <div style="font-weight:700; color:${{chunkObj.color.hex}}">${{cid}} (${{chunkObj.page_span_str}})</div>
            <div style="font-size:11px; color:#cbd5e1; margin-top:2px;">Type: ${{btype}} &bull; ~${{chunkObj.estimated_tokens}} tokens</div>
            ${{chunkObj.headings.length ? `<div style="font-size:11px; margin-top:4px; color:#93c5fd;"># ${{chunkObj.headings[0]}}</div>` : ""}}
          `;
          tooltip.style.display = "block";
          positionTooltip(e);
        }}
      }});

      box.addEventListener("mousemove", (e) => positionTooltip(e));

      box.addEventListener("mouseleave", () => {{
        tooltip.style.display = "none";
      }});

      box.addEventListener("click", (e) => {{
        e.stopPropagation();
        highlightChunk(cid, false, true);
      }});
    }});

    function positionTooltip(e) {{
      const x = e.clientX + 14;
      const y = e.clientY + 14;
      tooltip.style.left = Math.min(x, window.innerWidth - 290) + "px";
      tooltip.style.top = Math.min(y, window.innerHeight - 100) + "px";
    }}

    // 5. Expand / Collapse Text
    document.querySelectorAll(".toggle-expand-btn").forEach(btn => {{
      btn.addEventListener("click", (e) => {{
        e.stopPropagation();
        const target = document.getElementById(btn.dataset.target);
        if (target.classList.contains("expanded")) {{
          target.classList.remove("expanded");
          btn.innerHTML = "Expand full text &darr;";
        }} else {{
          target.classList.add("expanded");
          btn.innerHTML = "Collapse text &uarr;";
        }}
      }});
    }});

    // 6. Copy text
    document.querySelectorAll(".copy-btn").forEach(btn => {{
      btn.addEventListener("click", (e) => {{
        e.stopPropagation();
        const target = document.getElementById(btn.dataset.copyId);
        navigator.clipboard.writeText(target.textContent).then(() => {{
          const orig = btn.textContent;
          btn.textContent = "Copied!";
          btn.style.color = "#059669";
          setTimeout(() => {{
            btn.textContent = orig;
            btn.style.color = "";
          }}, 1500);
        }});
      }});
    }});

    // 7. Search & Page Filter
    function filterCards() {{
      const query = chunkSearch.value.toLowerCase().trim();
      const activePill = document.querySelector(".filter-pill.active");
      const pageFilter = activePill ? activePill.dataset.pageFilter : "all";

      let visibleCount = 0;

      document.querySelectorAll(".chunk-card").forEach(card => {{
        const cid = card.dataset.chunkId.toLowerCase();
        const startP = parseInt(card.dataset.startPage);
        const endP = parseInt(card.dataset.endPage);
        const text = card.textContent.toLowerCase();

        const matchesQuery = !query || text.includes(query) || cid.includes(query);
        let matchesPage = true;
        if (pageFilter !== "all") {{
          const targetP = parseInt(pageFilter);
          matchesPage = targetP >= startP && targetP <= endP;
        }}

        if (matchesQuery && matchesPage) {{
          card.style.display = "flex";
          visibleCount++;
        }} else {{
          card.style.display = "none";
        }}
      }});

      const filteredCountEl = document.getElementById("filtered-count");
      if (query || pageFilter !== "all") {{
        filteredCountEl.textContent = `Showing ${{visibleCount}} of ${{CHUNKS_DATA.length}}`;
      }} else {{
        filteredCountEl.textContent = "";
      }}
    }}

    chunkSearch.addEventListener("input", filterCards);

    document.querySelectorAll(".filter-pill").forEach(pill => {{
      pill.addEventListener("click", () => {{
        document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        filterCards();
      }});
    }});

    // 8. Reset View
    btnReset.addEventListener("click", () => {{
      setZoom(1.0);
      pageSelect.value = "all";
      document.querySelectorAll(".page-wrapper").forEach(el => el.style.display = "flex");
      chunkSearch.value = "";
      document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      document.querySelector('.filter-pill[data-page-filter="all"]').classList.add("active");
      filterCards();
      highlightChunk(null);
      viewerScroll.scrollTo({{ top: 0, behavior: "smooth" }});
      chunksList.scrollTo({{ top: 0, behavior: "smooth" }});
    }});
  </script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"[Dashboard] HTML visualization generated at: {output_path} ({file_size_kb:.1f} KB)")


def main():
    defaults = load_env_or_manifest()
    args = parse_arguments(defaults)

    if not args.pdf or not os.path.exists(args.pdf):
        sys.exit(
            f"Error: Input PDF not found at '{args.pdf}'. "
            "Please specify via --pdf <path> or configure INPUT_FILE_PATH in .env"
        )
    if not args.json or not os.path.exists(args.json):
        sys.exit(
            f"Error: Document AI JSON output not found at '{args.json}'. "
            "Please run batch_chunk.py first or specify via --json <path>"
        )

    print("=" * 65)
    print("Generating Document AI Chunking HTML Dashboard")
    print("=" * 65)
    print(f"PDF Input    : {args.pdf}")
    print(f"JSON Input   : {args.json}")
    print(f"HTML Output  : {args.output}")
    print("-" * 65)

    # 1. Parse Document AI JSON
    chunks_list, page_overlays = parse_docai_output(args.json)
    print(f"[Parser] Extracted {len(chunks_list)} chunks spanning {len(page_overlays)} pages.")

    # 2. Render PDF Pages
    pages = render_pdf_pages_to_images(args.pdf)

    # 3. Generate HTML Dashboard
    pdf_filename = os.path.basename(args.pdf)
    generate_html_dashboard(
        pdf_filename=pdf_filename,
        chunks=chunks_list,
        page_overlays=page_overlays,
        pages=pages,
        output_path=args.output,
    )

    print("=" * 65)
    print("VISUALIZATION DASHBOARD READY!")
    print(f"Open in browser: file://{os.path.abspath(args.output)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
