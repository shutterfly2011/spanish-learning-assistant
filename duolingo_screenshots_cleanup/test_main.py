import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
import importlib.util
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("main.py")
spec = importlib.util.spec_from_file_location("duolingo_main", MODULE_PATH)
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


class ResolveInputPathTests(unittest.TestCase):
    def test_resolve_single_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "sample.png"
            image_path.write_bytes(b"fake image")

            args = SimpleNamespace(file=str(image_path), folder=None)
            resolved_path, input_type = main.resolve_input_path(args)

            self.assertEqual(resolved_path, image_path.resolve())
            self.assertEqual(input_type, "file")

    def test_resolve_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = SimpleNamespace(file=None, folder=str(root))
            resolved_path, input_type = main.resolve_input_path(args)

            self.assertEqual(resolved_path, root.resolve())
            self.assertEqual(input_type, "folder")


class FlashcardFormattingTests(unittest.TestCase):
    def test_build_flashcard_includes_source_filename(self) -> None:
        flashcard = main.build_flashcard(
            "casa",
            "noun",
            {"meanings": [{"definition": "house"}]},
            "IMG_1234.PNG",
        )

        self.assertIn("Source: IMG_1234.PNG", flashcard)

    def test_append_to_markdown_skips_duplicate_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "flashcards.md"
            existing_card = main.build_flashcard(
                "casa", "noun", {"meanings": [{"definition": "house"}]}
            )
            output_path.write_text(existing_card + "\n", encoding="utf-8")
            duplicate = main.build_flashcard(
                "casa", "noun", {"meanings": [{"definition": "home"}]}
            )

            self.assertFalse(main.append_to_markdown(duplicate, output_path))
            self.assertEqual(output_path.read_text(encoding="utf-8"), existing_card + "\n")

    def test_append_to_markdown_appends_new_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "flashcards.md"
            existing_card = main.build_flashcard(
                "casa", "noun", {"meanings": [{"definition": "house"}]}
            )
            output_path.write_text(existing_card + "\n", encoding="utf-8")
            new_card = main.build_flashcard(
                "perro", "noun", {"meanings": [{"definition": "dog"}]}
            )

            self.assertTrue(main.append_to_markdown(new_card, output_path))
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("\nperro\n", content)


class OcrSidecarTests(unittest.TestCase):
    def test_existing_json_sidecar_skips_vision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.PNG"
            image_path.write_bytes(b"fake image")
            json_path = image_path.with_suffix(".json")
            json_path.write_text(
                json.dumps({"ocr_result": "[sentence] texto guardado"}),
                encoding="utf-8",
            )

            with patch.object(main, "extract_content") as extract_content:
                content = main.get_ocr_content(
                    image_path,
                    object(),
                    main.logging.getLogger("test"),
                )

            self.assertEqual(content, "[sentence] texto guardado")
            extract_content.assert_not_called()

    def test_vision_output_is_saved_to_json_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"

            with patch.object(main, "extract_content", return_value="[button] CONTINUE"):
                content = main.get_ocr_content(
                    image_path,
                    object(),
                    main.logging.getLogger("test"),
                )

            self.assertEqual(content, "[button] CONTINUE")
            results = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(results["ocr_result"], "[button] CONTINUE")
            self.assertIsNone(results["identification_result"])
            self.assertIsNone(results["lookup_result"])
            self.assertEqual(results["final_outcome"], "")

    def test_writes_identified_word_type_and_results_to_json_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            identification_result = {"is_spanish_lesson": True, "word": "anuncio"}
            lookup_result = {"meanings": [{"definition": "announcement"}]}

            main.write_processing_results(
                image_path,
                "[sentence] texto",
                "anuncio",
                "noun",
                identification_result,
                lookup_result,
            )

            self.assertEqual(
                json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8")),
                {
                    "ocr_result": "[sentence] texto",
                    "identified_word": "anuncio",
                    "word_type": "noun",
                    "identification_result": identification_result,
                    "lookup_result": lookup_result,
                    "final_outcome": "",
                },
            )


class ProcessingFailureTests(unittest.TestCase):
    def test_lookup_failure_does_not_process_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "sample.png"
            image_path.write_bytes(b"fake image")
            output_md = root / "flashcards.md"
            processed_dir = root / "processed"

            with (
                patch.object(main, "setup_logging", return_value=main.logging.getLogger("test")),
                patch.object(main, "build_config", return_value={
                    "provider": "test",
                    "vision_model": "test",
                    "text_model": "test",
                }),
                patch.object(main, "build_backend"),
                patch.object(main, "extract_content", return_value="anuncio"),
                patch.object(main, "process_with_rules", return_value={
                    "is_spanish_lesson": True,
                    "word": "anuncio",
                    "word_type": "noun",
                    "needs_lookup": True,
                }),
                patch.object(main, "lookup_word", side_effect=ConnectionError("lookup unavailable")),
                patch.object(main, "append_csv_row"),
            ):
                with patch.dict(
                    main.os.environ,
                    {
                        "INPUT_FILE": str(image_path),
                        "OUTPUT_MARKDOWN_FILE": str(output_md),
                        "OUTPUT_FOLDER": str(processed_dir),
                    },
                    clear=False,
                ), patch.object(main.sys, "argv", ["main.py"]):
                    main.main()

            self.assertTrue(image_path.exists())
            self.assertFalse((processed_dir / image_path.name).exists())
            self.assertFalse(output_md.exists())
            results = json.loads(
                image_path.with_suffix(".json").read_text(encoding="utf-8")
            )
            self.assertEqual(results["ocr_result"], "anuncio")
            self.assertEqual(results["identified_word"], "anuncio")
            self.assertEqual(results["word_type"], "noun")
            self.assertEqual(results["identification_result"]["word"], "anuncio")
            self.assertEqual(results["lookup_result"], {})
            self.assertEqual(results["final_outcome"], "lookup_failed")


if __name__ == "__main__":
    unittest.main()
