#!/usr/bin/env python3
"""
Batch Chunking Script using Google Cloud Document AI Layout Parser.

- Creates required GCS buckets if they do not exist.
- Uploads local document (or uses GCS URI).
- Configures Document AI Layout Parser with chunking enabled.
- Runs asynchronous batch processing job.
- Downloads resulting JSON chunks locally for inspection and visualization.
- Externalizes all settings to .env.
"""

import argparse
from datetime import datetime
import json
import os
import re
import sys
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from google.cloud import storage


def load_config() -> dict:
    """Load configuration from .env and environment variables."""
    load_dotenv()

    config = {
        "project_id": os.getenv("PROJECT_ID", "").strip(),
        "location": os.getenv("LOCATION", "us").strip().lower(),
        "processor_id": os.getenv("PROCESSOR_ID", "").strip(),
        "processor_version_id": os.getenv("PROCESSOR_VERSION_ID", "").strip() or None,
        "gcs_input_bucket": os.getenv("GCS_INPUT_BUCKET", "").strip(),
        "gcs_output_bucket": os.getenv("GCS_OUTPUT_BUCKET", "").strip(),
        "input_file_path": os.getenv("INPUT_FILE_PATH", "").strip(),
        "chunk_size": int(os.getenv("CHUNK_SIZE", "500")),
        "include_ancestor_headings": os.getenv("INCLUDE_ANCESTOR_HEADINGS", "true").lower() in ("true", "1", "yes"),
        "local_output_dir": os.getenv("LOCAL_OUTPUT_DIR", "./results").strip(),
    }
    return config


def parse_arguments(defaults: dict) -> argparse.Namespace:
    """Parse CLI arguments with .env values as defaults."""
    parser = argparse.ArgumentParser(
        description="Run Document AI Layout Parser batch chunking on documents."
    )
    parser.add_argument(
        "--project-id",
        default=defaults["project_id"],
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--location",
        default=defaults["location"],
        help="Document AI location ('us' or 'eu')",
    )
    parser.add_argument(
        "--processor-id",
        default=defaults["processor_id"],
        help="Document AI Layout Parser Processor ID",
    )
    parser.add_argument(
        "--processor-version-id",
        default=defaults["processor_version_id"],
        help="Optional specific processor version ID (leave empty for default)",
    )
    parser.add_argument(
        "--input-bucket",
        default=defaults["gcs_input_bucket"],
        help="GCS bucket name for input files",
    )
    parser.add_argument(
        "--output-bucket",
        default=defaults["gcs_output_bucket"],
        help="GCS bucket name for Document AI output results",
    )
    parser.add_argument(
        "--input-file",
        default=defaults["input_file_path"],
        help="Local PDF file path or GCS URI (gs://...)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=defaults["chunk_size"],
        help="Maximum token count per chunk (e.g. 250, 500, 1000)",
    )
    parser.add_argument(
        "--include-ancestor-headings",
        action="store_true",
        default=defaults["include_ancestor_headings"],
        help="Include ancestor heading context in chunk text",
    )
    parser.add_argument(
        "--local-output-dir",
        default=defaults["local_output_dir"],
        help="Directory to save downloaded Document AI JSON results",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1200,
        help="Timeout in seconds for Document AI batch operation (default 1200s)",
    )
    return parser.parse_args()


def ensure_bucket_exists(storage_client: storage.Client, bucket_name: str, location: str) -> storage.Bucket:
    """Check if GCS bucket exists; if not, create it."""
    try:
        bucket = storage_client.get_bucket(bucket_name)
        print(f"[GCS] Bucket '{bucket_name}' exists.")
        return bucket
    except Exception:
        # Map location string (e.g., 'eu' -> 'EU', 'us' -> 'US')
        loc_upper = location.upper()
        print(f"[GCS] Bucket '{bucket_name}' not found. Creating in location '{loc_upper}'...")
        try:
            bucket = storage_client.create_bucket(bucket_name, location=loc_upper)
            print(f"[GCS] Bucket '{bucket_name}' created successfully.")
            return bucket
        except Exception as e:
            print(f"[GCS] Error creating bucket '{bucket_name}': {e}", file=sys.stderr)
            raise


def prepare_input_document(
    storage_client: storage.Client,
    input_path: str,
    bucket_name: str,
) -> Tuple[str, str]:
    """
    Ensure input document is on GCS.
    If local, upload to GCS. Returns (gcs_uri, local_path_or_empty).
    """
    if input_path.startswith("gs://"):
        print(f"[Input] Using GCS URI directly: {input_path}")
        return input_path, ""

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found at: {input_path}")

    filename = os.path.basename(input_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    blob_name = f"inputs/{timestamp}_{filename}"

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    print(f"[Input] Uploading '{input_path}' to gs://{bucket_name}/{blob_name} ...")
    blob.upload_from_filename(input_path)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"[Input] Upload complete: {gcs_uri}")
    return gcs_uri, os.path.abspath(input_path)


def run_batch_chunking(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version_id: Optional[str],
    gcs_input_uri: str,
    gcs_output_uri: str,
    chunk_size: int,
    include_ancestor_headings: bool,
    timeout: int = 1200,
) -> Tuple[str, List[str]]:
    """Submit batch process request with chunking options and wait for completion."""
    opts = ClientOptions(
        api_endpoint=f"{location}-documentai.googleapis.com",
        quota_project_id=project_id,
    )
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # Input specification
    gcs_document = documentai.GcsDocument(
        gcs_uri=gcs_input_uri,
        mime_type="application/pdf",
    )
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_documents=documentai.GcsDocuments(documents=[gcs_document])
    )

    # Output specification
    output_config = documentai.DocumentOutputConfig(
        gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
            gcs_uri=gcs_output_uri
        )
    )

    # Layout Parser Chunking Configuration
    process_options = documentai.ProcessOptions(
        layout_config=documentai.ProcessOptions.LayoutConfig(
            chunking_config=documentai.ProcessOptions.LayoutConfig.ChunkingConfig(
                chunk_size=chunk_size,
                include_ancestor_headings=include_ancestor_headings,
            ),
            return_bounding_boxes=True,
            enable_table_annotation=True,
            enable_image_annotation=True,
        )
    )

    # Processor resource name
    if processor_version_id:
        processor_name = client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
    else:
        processor_name = client.processor_path(project_id, location, processor_id)

    request = documentai.BatchProcessRequest(
        name=processor_name,
        input_documents=input_config,
        document_output_config=output_config,
        process_options=process_options,
    )

    print(f"[DocAI] Submitting batch process request to {processor_name}...")
    operation = client.batch_process_documents(request=request)
    op_name = operation.operation.name
    print(f"[DocAI] Operation started: {op_name}")
    print(f"[DocAI] Waiting for batch operation to complete (timeout: {timeout}s)...")

    operation.result(timeout=timeout)
    print("[DocAI] Batch operation finished successfully!")

    metadata = documentai.BatchProcessMetadata(operation.metadata)
    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        raise RuntimeError(f"Batch processing failed: {metadata.state_message}")

    output_prefixes = []
    for proc in metadata.individual_process_statuses:
        output_prefixes.append(proc.output_gcs_destination)

    return op_name, output_prefixes


def download_batch_results(
    storage_client: storage.Client,
    output_gcs_destinations: List[str],
    local_output_dir: str,
) -> List[str]:
    """Download output JSON result files from GCS to local output directory."""
    os.makedirs(local_output_dir, exist_ok=True)
    downloaded_files = []

    for destination in output_gcs_destinations:
        match = re.match(r"gs://([^/]+)/(.*)", destination)
        if not match:
            print(f"[GCS] Warning: could not parse GCS path '{destination}'")
            continue

        bucket_name, prefix = match.groups()
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))

        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue
            local_filename = os.path.basename(blob.name)
            local_path = os.path.join(local_output_dir, local_filename)
            print(f"[GCS] Downloading result {blob.name} -> {local_path}")
            blob.download_to_filename(local_path)
            downloaded_files.append(local_path)

    return downloaded_files


def main():
    defaults = load_config()
    args = parse_arguments(defaults)

    if not args.project_id:
        sys.exit("Error: PROJECT_ID is not configured in .env or passed via --project-id.")
    if not args.processor_id:
        sys.exit("Error: PROCESSOR_ID is not configured in .env or passed via --processor-id.")
    if not args.input_bucket or not args.output_bucket:
        sys.exit("Error: GCS_INPUT_BUCKET and GCS_OUTPUT_BUCKET must be configured.")
    if not args.input_file:
        sys.exit("Error: INPUT_FILE_PATH is not configured in .env or passed via --input-file.")

    print("=" * 65)
    print("Document AI Layout Parser Batch Chunking")
    print("=" * 65)
    print(f"Project ID        : {args.project_id}")
    print(f"Location          : {args.location}")
    print(f"Processor ID      : {args.processor_id}")
    print(f"Input Bucket      : {args.input_bucket}")
    print(f"Output Bucket     : {args.output_bucket}")
    print(f"Input Document    : {args.input_file}")
    print(f"Chunk Size        : {args.chunk_size}")
    print(f"Ancestor Headings : {args.include_ancestor_headings}")
    print(f"Local Output Dir  : {args.local_output_dir}")
    print("-" * 65)

    storage_client = storage.Client(project=args.project_id)

    # 1. Ensure GCS Buckets exist
    ensure_bucket_exists(storage_client, args.input_bucket, args.location)
    if args.output_bucket != args.input_bucket:
        ensure_bucket_exists(storage_client, args.output_bucket, args.location)

    # 2. Upload / verify input document
    gcs_input_uri, local_input_path = prepare_input_document(
        storage_client, args.input_file, args.input_bucket
    )

    # 3. Setup output URI
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    gcs_output_uri = f"gs://{args.output_bucket}/outputs/{timestamp}/"

    # 4. Run batch chunking job
    op_name, output_destinations = run_batch_chunking(
        project_id=args.project_id,
        location=args.location,
        processor_id=args.processor_id,
        processor_version_id=args.processor_version_id,
        gcs_input_uri=gcs_input_uri,
        gcs_output_uri=gcs_output_uri,
        chunk_size=args.chunk_size,
        include_ancestor_headings=args.include_ancestor_headings,
        timeout=args.timeout,
    )

    # 5. Download results locally
    downloaded_files = download_batch_results(
        storage_client, output_destinations, args.local_output_dir
    )

    # 6. Count chunks and write metadata manifest
    total_chunks = 0
    primary_json = downloaded_files[0] if downloaded_files else ""
    if primary_json and os.path.exists(primary_json):
        with open(primary_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            chunks = data.get("chunkedDocument", {}).get("chunks", [])
            total_chunks = len(chunks)

    # If input document was a GCS URI and not local, download it locally for visualization
    pdf_for_visualization = local_input_path
    if not pdf_for_visualization and gcs_input_uri.startswith("gs://"):
        m = re.match(r"gs://([^/]+)/(.*)", gcs_input_uri)
        if m:
            b_name, b_path = m.groups()
            pdf_for_visualization = os.path.join(
                args.local_output_dir, os.path.basename(b_path)
            )
            print(f"[GCS] Downloading input PDF for visualizer -> {pdf_for_visualization}")
            storage_client.bucket(b_name).blob(b_path).download_to_filename(pdf_for_visualization)

    manifest_path = os.path.join(args.local_output_dir, "manifest.json")
    manifest_data = {
        "pdf_path": pdf_for_visualization,
        "gcs_input_uri": gcs_input_uri,
        "gcs_output_uri": gcs_output_uri,
        "operation_name": op_name,
        "json_files": downloaded_files,
        "primary_json": primary_json,
        "chunk_count": total_chunks,
        "chunk_size": args.chunk_size,
        "timestamp": timestamp,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print("\n" + "=" * 65)
    print("BATCH PROCESSING COMPLETED SUCCESSFULLY!")
    print("=" * 65)
    print(f"Chunks produced   : {total_chunks}")
    print(f"Results JSON      : {primary_json}")
    print(f"Input PDF Path    : {pdf_for_visualization}")
    print(f"Manifest File     : {manifest_path}")
    print("-" * 65)
    print("To visualize the chunks on the PDF, run:")
    print("  python3 visualize_chunks.py")
    print("=" * 65)


if __name__ == "__main__":
    main()
