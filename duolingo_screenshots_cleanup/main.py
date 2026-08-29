"""
Duolingo Screenshot Processor

Iterates over a folder of iPhone images, identifies Duolingo screenshots,
extracts the Spanish subject word via a vision model, looks it up via the
BuenoSpanish MCP server, and appends a concise flashcard to a Markdown file.

Usage:
    python main.py --folder /path/to/photos
    python main.py --file /path/to/image.png
    python main.py                          # uses INPUT_FOLDER from .env

Set PROVIDER in .env to switch between ollama / openai / gemini / bedrock.
"""

import argparse
import csv
import json
import logging
import os
import shutil
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

from processor import (
    IMAGE_EXTENSIONS,
    append_to_markdown,
    build_backend,
    build_flashcard,
    extract_content,
    is_screenshot,
    lookup_word,
    process_with_rules,
)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
RULES_FILE = Path(__file__).parent / "rules.md"


def setup_logging(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("processor")


def append_csv_row(csv_path: Path, file_name: str, vision_response: str, flashcard_output: str) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        if write_header:
            writer.writerow(["file name", "OCR/vision response", "Flashcard output"])
        writer.writerow([file_name, vision_response, flashcard_output])


def write_processing_results(
    image_path: Path,
    ocr_result: str,
    identified_word: str = "",
    word_type: str = "",
    identification_result: dict | None = None,
    lookup_result: dict | None = None,
    final_outcome: str = "",
) -> None:
    results = {
        "ocr_result": ocr_result,
        "identified_word": identified_word,
        "word_type": word_type,
        "identification_result": identification_result,
        "lookup_result": lookup_result,
        "final_outcome": final_outcome,
    }
    json_path = image_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_ocr_content(image_path: Path, backend, log: logging.Logger) -> str:
    json_path = image_path.with_suffix(".json")
    if json_path.exists():
        results = json.loads(json_path.read_text(encoding="utf-8"))
        content = results.get("ocr_result")
        # An empty cached result means a prior attempt failed (dead backend or an
        # empty model response) — retry instead of treating it as a valid hit,
        # otherwise the file gets stuck reporting the same failure forever.
        if isinstance(content, str) and content.strip():
            log.info(f"  [vision] using existing JSON sidecar {json_path.name}")
            return content

    log.info("  [vision] extracting content...")
    content = extract_content(image_path, backend)
    write_processing_results(image_path, content)
    log.info(f"  [vision] saved processing results to {json_path.name}")
    return content


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process Duolingo screenshots into Spanish flashcards."
    )
    parser.add_argument(
        "--folder",
        help="Path to the folder containing iPhone images. Overrides INPUT_FOLDER in .env.",
    )
    parser.add_argument(
        "--file",
        help="Path to a single image file to process. Overrides --folder and INPUT_FOLDER.",
    )
    return parser.parse_args()


def resolve_input_path(args: argparse.Namespace) -> tuple[Path, str]:
    file_str = args.file or os.getenv("INPUT_FILE", "")
    if file_str:
        file_path = Path(file_str).expanduser().resolve()
        if not file_path.exists():
            sys.exit(f"Error: file not found: {file_path}")
        if not file_path.is_file():
            sys.exit(f"Error: not a file: {file_path}")
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            sys.exit(f"Error: unsupported image extension: {file_path}")
        return file_path, "file"

    folder_str = args.folder or os.getenv("INPUT_FOLDER", "")
    if not folder_str:
        sys.exit(
            "Error: no input specified. "
            "Use --file /path/to/image.png, --folder /path/to/photos, or set INPUT_FOLDER in .env."
        )
    folder = Path(folder_str).expanduser().resolve()
    if not folder.exists():
        sys.exit(f"Error: folder not found: {folder}")
    if not folder.is_dir():
        sys.exit(f"Error: not a folder: {folder}")
    return folder, "folder"


def build_config() -> dict:
    provider = os.getenv("PROVIDER", "ollama").lower()
    config: dict = {"provider": provider}

    if provider == "ollama":
        config.update({
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "vision_model":    os.getenv("OLLAMA_VISION_MODEL", "llava:latest"),
            "text_model":      os.getenv("OLLAMA_MODEL", "llama3"),
        })
    elif provider == "openai":
        config.update({
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "vision_model":   os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
            "text_model":     os.getenv("OPENAI_MODEL", "gpt-4o"),
        })
    elif provider == "gemini":
        config.update({
            "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
            "vision_model":   os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-pro"),
            "text_model":     os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        })
    elif provider == "bedrock":
        config.update({
            "aws_region":      os.getenv("AWS_REGION", "us-east-1"),
            "vision_model":    os.getenv("BEDROCK_VISION_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            "text_model":      os.getenv("BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"),
            "bedrock_api_key": os.getenv("BEDROCK_API_KEY", ""),
        })
    else:
        sys.exit(f"Error: unknown PROVIDER '{provider}'. Choose: ollama, openai, gemini, bedrock.")

    return config


def main() -> None:
    args = parse_args()
    input_path, input_type = resolve_input_path(args)

    log = setup_logging(Path(__file__).parent / "processor.log")
    log.info("=" * 60)
    log.info("Starting Duolingo screenshot processor")
    log.info(f"Input {input_type}: {input_path}")

    config = build_config()
    backend = build_backend(config)

    provider = config["provider"]
    log.info(f"Provider     : {provider}")
    log.info(f"Vision model : {config['vision_model']}")
    log.info(f"Text model   : {config['text_model']}")

    if input_type == "file":
        default_output_md = input_path.parent / "flashcards.md"
        default_processed_dir = input_path.parent / "processed"
    else:
        default_output_md = input_path / "flashcards.md"
        default_processed_dir = input_path / "processed"

    output_md = Path(
        os.getenv("OUTPUT_MARKDOWN_FILE", str(default_output_md))
    ).expanduser().resolve()

    processed_dir = Path(
        os.getenv("OUTPUT_FOLDER", str(default_processed_dir))
    ).expanduser().resolve()
    processed_dir.mkdir(parents=True, exist_ok=True)

    csv_path = (input_path.parent if input_type == "file" else input_path) / "processing_results.csv"
    log.info(f"CSV output   : {csv_path}")

    log.info(f"Output file  : {output_md}")
    log.info(f"Processed dir: {processed_dir}")

    if not RULES_FILE.exists():
        log.error(f"rules.md not found at {RULES_FILE}. Cannot continue.")
        sys.exit(1)
    rules_text = RULES_FILE.read_text(encoding="utf-8")

    if input_type == "file":
        images = [input_path]
    else:
        images = sorted(
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        )

    batch_size = int(os.getenv("BATCH_SIZE", "12") or "0")
    if batch_size > 0:
        batches = [images[i:i + batch_size] for i in range(0, len(images), batch_size)]
    else:
        batches = [images] if images else []

    log.info(f"Found {len(images)} image(s) to process")
    if len(batches) > 1:
        log.info(f"Processing in {len(batches)} batch(es) of up to {batch_size}")

    ok_count = skipped_count = error_count = 0

    # Two passes per batch, one per model, so the vision model and text model
    # each load onto the GPU once per batch instead of swapping per image.
    for batch_num, batch_images in enumerate(batches, start=1):
        if len(batches) > 1:
            log.info("=" * 60)
            log.info(f"Batch {batch_num}/{len(batches)} — {len(batch_images)} image(s)")

        pending: list[tuple[Path, str]] = []

        log.info("=" * 60)
        log.info(f"Stage 1/2 — vision extraction ({config['vision_model']})")
        for img_path in batch_images:
            log.info(f"--- {img_path.name}")
            try:
                if not is_screenshot(img_path):
                    log.info("  [skip] not a screenshot (camera EXIF present)")
                    write_processing_results(img_path, "", final_outcome="not_screenshot")
                    skipped_count += 1
                    append_csv_row(csv_path, img_path.name, "", "")
                    continue

                content = get_ocr_content(img_path, backend, log)
                if not content.strip():
                    log.warning("  [skip] vision model returned empty content")
                    write_processing_results(img_path, content, final_outcome="empty_ocr")
                    skipped_count += 1
                    append_csv_row(csv_path, img_path.name, content, "")
                    continue
                print(f"\n  ── OCR result ──\n{content}\n  ────────────────")
                pending.append((img_path, content))

            except requests.exceptions.RequestException as exc:
                log.error(f"  [fatal] vision backend unreachable: {exc}")
                log.error(
                    "  Aborting run instead of burning through the remaining images "
                    "against a dead backend — no .json sidecar was written for this "
                    "image, so it will be retried on the next run."
                )
                append_csv_row(csv_path, img_path.name, "", "")
                sys.exit(1)
            except Exception as exc:
                write_processing_results(img_path, "", final_outcome="error")
                log.error(f"  [error] {exc}", exc_info=True)
                error_count += 1
                append_csv_row(csv_path, img_path.name, "", "")

        log.info("=" * 60)
        log.info(f"Stage 2/2 — rule-based identification ({config['text_model']})")
        for img_path, content in pending:
            log.info(f"--- {img_path.name}")
            flashcard_output = ""
            result = None
            word = ""
            word_type = ""
            lookup_data: dict = {}
            final_outcome = "error"

            try:
                # ── Step 3: Apply rules ───────────────────────────────────────
                log.info("  [rules] identifying word and type...")
                result = process_with_rules(content, rules_text, backend)
                write_processing_results(
                    img_path,
                    content,
                    identification_result=result,
                    final_outcome="identification_failed" if not result else "",
                )
                if not result:
                    log.warning("  [skip] could not parse rules response")
                    skipped_count += 1
                    continue
                if not result.get("is_spanish_lesson"):
                    log.info("  [skip] not identified as a Spanish lesson")
                    write_processing_results(
                        img_path,
                        content,
                        identification_result=result,
                        final_outcome="not_spanish_lesson",
                    )
                    skipped_count += 1
                    continue

                word = (result.get("word") or "").strip()
                word_type = (result.get("word_type") or "").strip()
                if not word or word.lower() == "null":
                    log.info("  [skip] no subject word identified")
                    write_processing_results(
                        img_path,
                        content,
                        word_type=word_type,
                        identification_result=result,
                        final_outcome="no_word",
                    )
                    skipped_count += 1
                    continue

                log.info(f"  word='{word}'  type='{word_type}'")

                # ── Step 3b: BuenoSpanish lookup ─────────────────────────────
                write_processing_results(
                    img_path,
                    content,
                    identified_word=word,
                    word_type=word_type,
                    identification_result=result,
                    lookup_result=lookup_data,
                )
                if result.get("needs_lookup", True):
                    log.info(f"  [lookup] looking up '{word}'...")
                    try:
                        lookup_data = lookup_word(word)
                    except Exception:
                        final_outcome = "lookup_failed"
                        raise
                    log.info(
                        f"  [lookup] meanings={len(lookup_data.get('meanings', []))}, "
                        f"etymology={'yes' if lookup_data.get('etymology') else 'no'}, "
                        f"cognates={lookup_data.get('english_cognates', [])}"
                    )
                    write_processing_results(
                        img_path,
                        content,
                        identified_word=word,
                        word_type=word_type,
                        identification_result=result,
                        lookup_result=lookup_data,
                    )

                # ── Step 4: Build and append flashcard ────────────────────────
                flashcard = build_flashcard(word, word_type, lookup_data, img_path.name)
                flashcard_output = flashcard
                appended = append_to_markdown(flashcard, output_md)
                final_outcome = "added" if appended else "duplicate"
                write_processing_results(
                    img_path,
                    content,
                    identified_word=word,
                    word_type=word_type,
                    identification_result=result,
                    lookup_result=lookup_data,
                    final_outcome=final_outcome,
                )
                if appended:
                    log.info(f"  [output] flashcard appended to {output_md.name}")
                else:
                    log.info(f"  [output] duplicate word '{word}', flashcard skipped")

                # ── Step 5: Move to output folder ─────────────────────────────
                dest = processed_dir / img_path.name
                if dest.exists():
                    dest = processed_dir / f"{img_path.stem}_dup{img_path.suffix}"
                shutil.move(str(img_path), str(dest))
                log.info(f"  [done] moved to {dest}")

                json_path = img_path.with_suffix(".json")
                if json_path.exists():
                    json_dest = dest.with_suffix(".json")
                    shutil.move(str(json_path), str(json_dest))
                    log.info(f"  [done] moved JSON sidecar to {json_dest}")
                ok_count += 1

            except requests.exceptions.RequestException as exc:
                log.error(f"  [fatal] backend unreachable: {exc}")
                log.error(
                    "  Aborting run instead of burning through the remaining images "
                    "against a dead backend — this image's OCR sidecar stays cached "
                    "and identification will be retried on the next run."
                )
                sys.exit(1)
            except Exception as exc:
                write_processing_results(
                    img_path,
                    content,
                    identified_word=word,
                    word_type=word_type,
                    identification_result=result,
                    lookup_result=lookup_data,
                    final_outcome=final_outcome,
                )
                log.error(f"  [error] {exc}", exc_info=True)
                error_count += 1
            finally:
                append_csv_row(csv_path, img_path.name, content, flashcard_output)

    log.info("=" * 60)
    log.info(
        f"Finished — processed: {ok_count}, "
        f"skipped: {skipped_count}, "
        f"errors: {error_count}"
    )


if __name__ == "__main__":
    main()
