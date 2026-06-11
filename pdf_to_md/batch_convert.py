"""
Batch PDF to Markdown Converter

Uses the marker library to convert PDF papers into well-structured Markdown files
suitable for downstream literature review workflows.

Dependencies:
    pip install marker-pdf torch

Model download:
    Models are downloaded automatically on first run (~3-5 GB total).
    Set the MARKER_MODEL_DIR environment variable to control cache location.
    Default: ~/.cache/marker/

Usage:
    python batch_convert.py --input /path/to/pdfs --output /path/to/markdown
    python batch_convert.py --input ./papers --output ./md_papers --batch-size 3
"""

import os
import sys
import glob
import time
import gc
import argparse
from pathlib import Path


def setup_environment(model_dir: str | None = None, device: str = "cuda"):
    """Configure environment variables before importing marker."""
    if model_dir:
        os.environ["MODEL_CACHE_DIR"] = str(model_dir)

    # Quantization reduces memory usage significantly (recommended for most users)
    if "FOUNDATION_MODEL_QUANTIZE" not in os.environ:
        os.environ["FOUNDATION_MODEL_QUANTIZE"] = "true"

    os.environ["TORCH_DEVICE"] = device

    # Threading optimizations
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def build_converter(output_dir: str, device: str = "cuda"):
    """Build a marker converter with optimized batch sizes.

    The converter and models are created once and reused across all PDFs,
    avoiding the overhead of reloading models for each file.
    """
    from marker.config.parser import ConfigParser
    from marker.models import create_model_dict
    from marker.output import save_output

    os.makedirs(output_dir, exist_ok=True)

    models = create_model_dict(device=device)

    config_parser = ConfigParser({
        "output_dir": output_dir,
        "disable_image_extraction": True,
        "output_format": "markdown",
        "recognition_batch_size": 8,
        "layout_batch_size": 8,
        "detection_batch_size": 4,
        "table_rec_batch_size": 8,
        "equation_batch_size": 8,
        "pdftext_workers": 1,
        "detector_postprocessing_cpu_workers": 2,
        "disable_multiprocessing": False,
    })

    converter_cls = config_parser.get_converter_cls()
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )

    return config_parser, converter, save_output


def convert_single(pdf_path: str, output_dir: str, config_parser, converter, save_output) -> bool:
    """Convert a single PDF file to Markdown.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory for output Markdown files.
        config_parser: Marker ConfigParser instance.
        converter: Marker converter instance.
        save_output: Marker save_output function.

    Returns:
        True on success, False on failure.
    """
    try:
        rendered = converter(pdf_path)
        out_folder = config_parser.get_output_folder(pdf_path)
        save_output(rendered, out_folder, config_parser.get_base_filename(pdf_path))

        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()

        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def process_all_pdfs(
    input_dir: str,
    output_dir: str,
    batch_size: int = 5,
    batch_delay: int = 10,
    device: str = "cuda",
):
    """Batch convert all PDFs in a directory to Markdown.

    Processes PDFs in batches to manage GPU/CPU memory. Between batches,
    a configurable delay allows the OS to release fragmented memory.

    Args:
        input_dir: Directory containing PDF files.
        output_dir: Directory for output Markdown files.
        batch_size: Number of PDFs to process per batch (default: 5).
        batch_delay: Seconds to wait between batches for memory release (default: 10).
    """
    os.makedirs(output_dir, exist_ok=True)

    pdf_files = sorted(glob.glob(os.path.join(input_dir, "*.pdf")))

    if not pdf_files:
        print(f"[INFO] No PDF files found in {input_dir}")
        return

    print("=" * 60)
    print("Batch PDF to Markdown Converter")
    print("=" * 60)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Found:  {len(pdf_files)} PDF files")
    print(f"Batch:  {batch_size} files, {batch_delay}s delay between batches")
    print("=" * 60)

    # Filter: skip already-processed files
    files_to_process = []
    skip_count = 0
    for pdf_file in pdf_files:
        pdf_name = os.path.splitext(os.path.basename(pdf_file))[0]
        expected_folder = os.path.join(output_dir, pdf_name)
        if os.path.exists(expected_folder):
            skip_count += 1
        else:
            files_to_process.append((pdf_file, pdf_name))

    total = len(files_to_process)
    if total == 0:
        print(f"[INFO] All {len(pdf_files)} files already processed. Nothing to do.")
        return

    print(f"To process: {total}")
    print(f"Skipped:    {skip_count} (already exist)")
    print("[INFO] Loading marker models (one-time)...")

    config_parser, converter, save_output_fn = build_converter(output_dir, device=device)

    print("[INFO] Models loaded. Starting conversion...")
    print("=" * 60)

    success, fail = 0, 0
    start_time = time.time()

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_files = files_to_process[batch_start:batch_end]
        batch_num = batch_start // batch_size + 1

        print(f"\n--- Batch {batch_num} ({batch_start + 1}-{batch_end} of {total}) ---")

        for idx, (pdf_file, pdf_name) in enumerate(batch_files, 1):
            global_idx = batch_start + idx
            print(f"[{global_idx}/{total}] {pdf_name} ...", end=" ", flush=True)

            if convert_single(pdf_file, output_dir, config_parser, converter, save_output_fn):
                success += 1
                print("OK")
            else:
                fail += 1
                print("FAIL")

        if batch_end < total:
            print(f"\n[INFO] Waiting {batch_delay}s for memory release...")
            time.sleep(batch_delay)

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Success:  {success}")
    print(f"  Failed:   {fail}")
    print(f"  Skipped:  {skip_count}")
    print(f"  Time:     {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Output:   {output_dir}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Batch convert PDF papers to Markdown using marker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_convert.py --input ./papers --output ./md_papers
  python batch_convert.py --input ./papers --output ./md_papers --batch-size 3 --device cpu
  python batch_convert.py --input ./papers --output ./md_papers --model-dir /data/marker_models
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Directory containing PDF files")
    parser.add_argument("--output", "-o", required=True, help="Directory for output Markdown files")
    parser.add_argument("--batch-size", type=int, default=5, help="PDFs per batch (default: 5)")
    parser.add_argument("--batch-delay", type=int, default=10, help="Seconds between batches (default: 10)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu", "mps"], help="Compute device (default: auto)")
    parser.add_argument("--model-dir", default=None, help="Marker model cache directory")
    parser.add_argument("--no-quantize", action="store_true", help="Disable model quantization (uses more memory)")

    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"Error: input directory not found: {args.input}")
        sys.exit(1)

    if args.device == "auto":
        import torch
        if torch.cuda.is_available():
            args.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            args.device = "mps"
        else:
            args.device = "cpu"

    if args.no_quantize:
        os.environ["FOUNDATION_MODEL_QUANTIZE"] = "false"

    setup_environment(model_dir=args.model_dir, device=args.device)

    process_all_pdfs(
        input_dir=args.input,
        output_dir=args.output,
        batch_size=args.batch_size,
        batch_delay=args.batch_delay,
        device=args.device,
    )


if __name__ == "__main__":
    main()
