"""
Duolingo Screenshot Processor

Iterates over a folder of iPhone images, identifies Duolingo screenshots,
extracts the Spanish subject word via an Ollama vision model, looks it up
via the BuenoSpanish MCP server, and appends a concise flashcard to a
Markdown file.

Usage:
    python main.py --folder /path/to/photos
    python main.py                          # uses INPUT_FOLDER from .env
"""

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from processor import (
    IMAGE_EXTENSIONS,
    append_to_markdown,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process Duolingo screenshots into Spanish flashcards."
    )
    parser.add_argument(
        "--folder",
        help="Path to the folder containing iPhone images. Overrides INPUT_FOLDER in .env.",
    )
    return parser.parse_args()


def resolve_folder(args: argparse.Namespace) -> Path:
    folder_str = args.folder or os.getenv("INPUT_FOLDER", "")
    if not folder_str:
        sys.exit(
            "Error: no folder specified. "
            "Use --folder /path or set INPUT_FOLDER in .env."
        )
    folder = Path(folder_str).expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"Error: folder not found: {folder}")
    return folder


def main() -> None:
    args = parse_args()
    folder = resolve_folder(args)

    log = setup_logging(Path(__file__).parent / "processor.log")
    log.info("=" * 60)
    log.info("Starting Duolingo screenshot processor")
    log.info(f"Input folder : {folder}")

    # Config from environment
    config = {
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "vision_model":    os.getenv("OLLAMA_VISION_MODEL", "llava:latest"),
        "text_model":      os.getenv("OLLAMA_MODEL", "llama3"),
        "mcp_server_url":  os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
    }
    output_md = Path(
        os.getenv("OUTPUT_MARKDOWN_FILE", str(folder / "flashcards.md"))
    ).expanduser().resolve()

    log.info(f"Vision model : {config['vision_model']} @ {config['ollama_base_url']}")
    log.info(f"Text model   : {config['text_model']}")
    log.info(f"MCP server   : {config['mcp_server_url']}")
    log.info(f"Output file  : {output_md}")

    # Load rules once
    if not RULES_FILE.exists():
        log.error(f"rules.md not found at {RULES_FILE}. Cannot continue.")
        sys.exit(1)
    rules_text = RULES_FILE.read_text(encoding="utf-8")

    # Prepare processed/ subfolder
    processed_dir = folder / "processed"
    processed_dir.mkdir(exist_ok=True)

    # Collect images (only from the root of the folder, not processed/)
    images = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )
    log.info(f"Found {len(images)} image(s) to process")

    ok_count = skipped_count = error_count = 0

    for img_path in images:
        log.info(f"--- {img_path.name}")

        try:
            # ── Step 1: Is it a screenshot? ──────────────────────────────
            if not is_screenshot(img_path):
                log.info("  [skip] not a screenshot (camera EXIF present)")
                skipped_count += 1
                continue

            # ── Step 2: Extract content via vision model ─────────────────
            log.info("  [vision] extracting content...")
            content = extract_content(
                img_path,
                config["ollama_base_url"],
                config["vision_model"],
            )
            if not content.strip():
                log.warning("  [skip] vision model returned empty content")
                skipped_count += 1
                continue
            log.debug(f"  content preview: {content[:200]!r}")

            # ── Step 3: Apply rules ───────────────────────────────────────
            log.info("  [rules] identifying word and type...")
            result = process_with_rules(
                content,
                rules_text,
                config["ollama_base_url"],
                config["text_model"],
            )
            if not result:
                log.warning("  [skip] could not parse rules response")
                skipped_count += 1
                continue
            if not result.get("is_spanish_lesson"):
                log.info("  [skip] not identified as a Spanish lesson")
                skipped_count += 1
                continue

            word = (result.get("word") or "").strip()
            word_type = (result.get("word_type") or "").strip()
            if not word or word.lower() == "null":
                log.info("  [skip] no subject word identified")
                skipped_count += 1
                continue

            log.info(f"  word='{word}'  type='{word_type}'")

            # ── Step 3b: MCP lookup ───────────────────────────────────────
            mcp_data: dict = {}
            if result.get("needs_lookup", True):
                log.info(f"  [mcp] looking up '{word}'...")
                try:
                    mcp_data = lookup_word(word, config["mcp_server_url"])
                    log.info(
                        f"  [mcp] meanings={len(mcp_data.get('meanings', []))}, "
                        f"etymology={'yes' if mcp_data.get('etymology') else 'no'}, "
                        f"cognates={mcp_data.get('english_cognates', [])}"
                    )
                except Exception as exc:
                    log.warning(f"  [mcp] lookup failed ({exc}); proceeding without it")

            # ── Step 4: Build and append flashcard ────────────────────────
            flashcard = build_flashcard(word, word_type, mcp_data)
            append_to_markdown(flashcard, output_md)
            log.info(f"  [output] flashcard appended to {output_md.name}")

            # ── Step 5: Move to processed/ ────────────────────────────────
            dest = processed_dir / img_path.name
            if dest.exists():
                dest = processed_dir / f"{img_path.stem}_dup{img_path.suffix}"
            shutil.move(str(img_path), str(dest))
            log.info(f"  [done] moved to processed/{dest.name}")
            ok_count += 1

        except Exception as exc:
            log.error(f"  [error] {exc}", exc_info=True)
            error_count += 1

    log.info("=" * 60)
    log.info(
        f"Finished — processed: {ok_count}, "
        f"skipped: {skipped_count}, "
        f"errors: {error_count}"
    )


if __name__ == "__main__":
    main()
