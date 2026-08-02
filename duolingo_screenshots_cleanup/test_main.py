import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import importlib.util


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


if __name__ == "__main__":
    unittest.main()
