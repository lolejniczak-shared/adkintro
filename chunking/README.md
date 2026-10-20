# Document AI Layout Parser Batch Chunking & HTML Visualization

A simple, modular two-script solution to process documents with Google Cloud Document AI's **Gemini Layout Parser Processor**, generate context-aware chunks with structural layout grounding, and inspect the resulting chunks overlaid on the original PDF via an interactive HTML dashboard.

---

## 📁 Project Architecture

```
chunking/
├── .env                     # Externalized configuration (project, buckets, processor, chunk settings)
├── .env.example             # Template configuration file
├── requirements.txt         # Python dependencies
├── batch_chunk.py           # SCRIPT 1: Creates GCS buckets, runs batch job with layout chunking
├── visualize_chunks.py      # SCRIPT 2: Parses results and builds interactive HTML dashboard
├── sample_5pages.pdf        # Sample document for testing
└── results/                 # Downloaded Document AI JSON, manifest, and generated HTML dashboard
    ├── manifest.json
    ├── <job_id>-0.json
    └── dashboard.html
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

*(Ensure you are authenticated with Google Cloud: `gcloud auth application-default login`)*

### 2. Configure Settings in `.env`
Edit `.env` (or copy from `.env.example`):
```env
PROJECT_ID=genai-app-builder
LOCATION=eu
PROCESSOR_ID=4d0315bdac12d002
PROCESSOR_VERSION_ID=

GCS_INPUT_BUCKET=genai-app-builder-docai-chunking
GCS_OUTPUT_BUCKET=genai-app-builder-docai-chunking

INPUT_FILE_PATH=./sample_5pages.pdf
CHUNK_SIZE=150
INCLUDE_ANCESTOR_HEADINGS=true

LOCAL_OUTPUT_DIR=./results
DASHBOARD_HTML_PATH=./results/dashboard.html
```

### 3. Step 1: Run the Batch Chunking Job
```bash
python3 batch_chunk.py
```
What this script does:
- Checks if the input and output GCS buckets exist; creates them automatically if they don't.
- Uploads the input PDF to Cloud Storage (if a local path is provided).
- Triggers Document AI `batch_process_documents` with:
  - `LayoutConfig.chunking_config` (`chunk_size`, `include_ancestor_headings=True`)
  - `return_bounding_boxes=True`
  - `enable_table_annotation=True`
  - `enable_image_annotation=True`
- Waits for the batch job operation to finish.
- Downloads the output JSON file(s) into `./results/` and writes `./results/manifest.json`.

You can also pass CLI arguments to override `.env` values at any time:
```bash
python3 batch_chunk.py --input-file ./my_document.pdf --chunk-size 250
```

### 4. Step 2: Generate the HTML Dashboard
```bash
python3 visualize_chunks.py
```
What this script does:
- Auto-detects the input PDF and JSON result from `./results/manifest.json` (or `.env`).
- Parses all chunks, hierarchical layout blocks, and normalized bounding box vertices.
- Renders PDF pages into optimized, embedded images.
- Generates a self-contained, standalone `dashboard.html` in `./results/`.

You can also specify explicit paths via CLI arguments:
```bash
python3 visualize_chunks.py --pdf ./sample_5pages.pdf --json ./results/my-output.json --output ./results/dashboard.html
```

---

## 🖥️ Interactive HTML Dashboard Features

Open `file:///home/user/prepday1/chunking/results/dashboard.html` in any modern web browser:

1. **Split-Screen Layout**:
   - **Left Panel**: High-resolution rendered PDF pages with synchronized colored bounding box overlays.
   - **Right Panel**: Chunks Explorer with metadata cards for each extracted chunk.
2. **Bi-directional Highlighting**:
   - **Hovering a chunk card** in the sidebar highlights all its corresponding bounding box blocks on the PDF page.
   - **Clicking a chunk card** smoothly scrolls the PDF viewer directly to the chunk's position on the page and triggers a subtle pulse ring.
   - **Hovering a bounding box on the PDF** reveals a floating tooltip showing Chunk ID, page range, block type (heading, paragraph, table, list, image), and ancestor headings, while highlighting the corresponding card in the sidebar.
3. **Chunk Content & Ancestor Headings**:
   - Shows extracted section headers (`# Heading`) preserved by Document AI.
   - Estimated token count and character counts per chunk.
   - Expandable full-text preview with one-click **"Copy text"** button.
4. **Interactive Controls**:
   - **Page Filter**: Filter by individual pages (e.g., P1, P2, P3) or view All Pages.
   - **Live Text Search**: Search chunk text, headings, or IDs in real time.
   - **Zoom Controls**: Zoom in / out (60% to 220%) with auto-centering.
   - **Overlays Toggle**: Toggle chunk overlays and chunk ID badges on/off.
   - **100% Standalone**: Self-contained single HTML file with embedded page graphics; requires no web server and works completely offline without CORS restrictions.
