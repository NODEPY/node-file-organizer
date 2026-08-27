import tempfile
import unittest
from pathlib import Path

from organizer import get_category, get_free_name, should_ignore


class OrganizerTest(unittest.TestCase):
    def test_category_is_selected_by_extension(self):
        self.assertEqual(get_category(Path("photo.PNG")), "Images")
        self.assertEqual(get_category(Path("project.py")), "Code")
        self.assertEqual(get_category(Path("unknown.file")), "Other")

    def test_temporary_downloads_are_ignored(self):
        self.assertTrue(should_ignore(Path("video.mp4.part")))
        self.assertTrue(should_ignore(Path(".hidden.txt")))
        self.assertFalse(should_ignore(Path("document.pdf")))

    def test_duplicate_file_gets_a_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original = Path(temp_dir) / "photo.jpg"
            original.touch()

            self.assertEqual(
                get_free_name(original),
                Path(temp_dir) / "photo_1.jpg",
            )


if __name__ == "__main__":
    unittest.main()
